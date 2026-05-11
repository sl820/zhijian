import logging
import os
import numpy as np
from typing import Optional

# Disable TorchDynamo/Triton before importing torch
os.environ["TORCHDYNAMO_DISABLE"] = "1"
os.environ["TORCH_COMPIZE_DISABLE"] = "1"

# Use Chinese mirror for HuggingFace models
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

from sklearn.metrics.pairwise import cosine_similarity
import torch

# Disable TorchDynamo/Triton to avoid "triton not installed" errors in some environments
try:
    import torch._dynamo
    torch._dynamo.config.disable = True
    torch._dynamo.config.suppress_errors = True
except Exception:
    pass

from transformers import BertTokenizer, BertModel

logger = logging.getLogger(__name__)


class SemanticAligner:
    def __init__(self, model_name: str = "bert-base-chinese", device: str = None):
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device
        self.use_amp = device == "cuda"  # Enable AMP on GPU
        self.amp_scaler = None

        logger.info(f"Loading BERT model '{model_name}' on {device}")
        logger.info(f"AMP (Automatic Mixed Precision) enabled: {self.use_amp}")

        # Enable cuDNN benchmark for faster convolutions
        if device == "cuda":
            torch.backends.cudnn.benchmark = True

        self.tokenizer = BertTokenizer.from_pretrained(model_name)
        self.model = BertModel.from_pretrained(model_name).to(device)
        self.model.eval()

        # Try to use torch.compile for PyTorch 2.0+ speedup
        if hasattr(torch, 'compile'):
            try:
                logger.info("Compiling model with torch.compile() for ~30% speedup...")
                self.model = torch.compile(self.model, mode="reduce-overhead")
                logger.info("Model compiled successfully")
            except Exception as e:
                logger.warning(f"torch.compile() failed: {e}, trying eager backend...")
                try:
                    self.model = torch.compile(self.model, backend="eager")
                    logger.info("Model compiled with eager backend")
                except Exception as e2:
                    logger.warning(f"torch.compile(eager) also failed: {e2}, using uncompiled model")

        # Initialize AMP scaler
        if self.use_amp:
            self.amp_scaler = torch.cuda.amp.GradScaler()

    def encode_sentences(self, sentences: list, batch_size: int = 32) -> np.ndarray:
        """Batch encode sentences using BERT [CLS] token with AMP optimization.

        Args:
            sentences: List of sentences to encode
            batch_size: Number of sentences per batch (smaller values use less GPU memory)
        """
        if not sentences:
            return np.array([])

        all_embeddings = []
        total_batches = (len(sentences) + batch_size - 1) // batch_size

        for i in range(0, len(sentences), batch_size):
            batch = sentences[i:i + batch_size]
            inputs = self.tokenizer(
                batch,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=512
            ).to(self.device)

            with torch.no_grad():
                if self.use_amp:
                    with torch.cuda.amp.autocast():
                        outputs = self.model(**inputs)
                else:
                    outputs = self.model(**inputs)
                cls_embeddings = outputs.last_hidden_state[:, 0, :].cpu().numpy()
                all_embeddings.append(cls_embeddings)

        return np.vstack(all_embeddings)

    def cosine_similarity_matrix(self, embeddings_a: np.ndarray, embeddings_b: np.ndarray) -> np.ndarray:
        return cosine_similarity(embeddings_a, embeddings_b)

    def needleman_wunsch(
        self,
        sim_matrix: np.ndarray,
        gap_penalty: float = -0.5,
        match_bonus: float = 1.0,
        mismatch_penalty: float = -0.5
    ) -> list:
        n, m = sim_matrix.shape
        dp = np.full((n + 1, m + 1), -np.inf)
        dp[0, 0] = 0.0

        for i in range(1, n + 1):
            dp[i, 0] = i * gap_penalty
        for j in range(1, m + 1):
            dp[0, j] = j * gap_penalty

        for i in range(1, n + 1):
            for j in range(1, m + 1):
                match_score = sim_matrix[i - 1, j - 1] * match_bonus
                diag = dp[i - 1, j - 1] + match_score
                up = dp[i - 1, j] + gap_penalty
                left = dp[i, j - 1] + gap_penalty
                dp[i, j] = max(diag, up, left)

        alignment = []
        i, j = n, m
        while i > 0 or j > 0:
            if i > 0 and j > 0:
                match_score = sim_matrix[i - 1, j - 1] * match_bonus
                diag = dp[i - 1, j - 1] + match_score
                up = dp[i - 1, j] + gap_penalty
                left = dp[i, j - 1] + gap_penalty

                if dp[i, j] == diag:
                    alignment.append((i - 1, j - 1))
                    i -= 1
                    j -= 1
                elif dp[i, j] == up:
                    alignment.append((i - 1, None))
                    i -= 1
                else:
                    alignment.append((None, j - 1))
                    j -= 1
            elif i > 0:
                alignment.append((i - 1, None))
                i -= 1
            else:
                alignment.append((None, j - 1))
                j -= 1

        alignment.reverse()
        return alignment

    def constrained_align(
        self,
        sentences_a: list,
        sentences_b: list,
        similarity_threshold: float = 0.7
    ) -> dict:
        if not sentences_a or not sentences_b:
            return {
                "alignments": [],
                "unmatched_a": list(range(len(sentences_a))) if sentences_a else [],
                "unmatched_b": list(range(len(sentences_b))) if sentences_b else [],
                "alignment_score": 0.0
            }

        embeddings_a = self.encode_sentences(sentences_a)
        embeddings_b = self.encode_sentences(sentences_b)
        sim_matrix = self.cosine_similarity_matrix(embeddings_a, embeddings_b)

        n, m = sim_matrix.shape
        dp = np.full((n + 1, m + 1), -np.inf)
        dp[0, 0] = 0.0

        for i in range(1, n + 1):
            dp[i, 0] = i * -0.5
        for j in range(1, m + 1):
            dp[0, j] = j * -0.5

        for i in range(1, n + 1):
            for j in range(1, m + 1):
                match_score = sim_matrix[i - 1, j - 1]
                diag = dp[i - 1, j - 1] + match_score
                up = dp[i - 1, j] - 0.5
                left = dp[i, j - 1] - 0.5
                dp[i, j] = max(diag, up, left)

        alignments = []
        alignment_set = set()
        i, j = n, m
        while i > 0 and j > 0:
            match_score = sim_matrix[i - 1, j - 1]
            diag = dp[i - 1, j - 1] + match_score
            up = dp[i - 1, j] - 0.5
            left = dp[i, j - 1] - 0.5

            if dp[i, j] == diag and match_score >= similarity_threshold:
                alignments.append((i - 1, j - 1, float(match_score)))
                alignment_set.add((i - 1, j - 1))
                i -= 1
                j -= 1
            elif dp[i, j] == up:
                i -= 1
            elif dp[i, j] == left:
                j -= 1
            else:
                if match_score >= similarity_threshold:
                    alignments.append((i - 1, j - 1, float(match_score)))
                    alignment_set.add((i - 1, j - 1))
                i -= 1
                j -= 1

        alignments.reverse()

        unmatched_a = [idx for idx in range(n) if idx not in {a[0] for a in alignments}]
        unmatched_b = [idx for idx in range(m) if idx not in {a[1] for a in alignments}]

        alignment_score = float(dp[n, m]) / max(n, m) if max(n, m) > 0 else 0.0

        return {
            "alignments": alignments,
            "unmatched_a": unmatched_a,
            "unmatched_b": unmatched_b,
            "alignment_score": alignment_score
        }

    def align_chapters(self, chapters_a: list, chapters_b: list) -> list:
        if not chapters_a or not chapters_b:
            return []

        embeddings_a = self.encode_sentences(chapters_a)
        embeddings_b = self.encode_sentences(chapters_b)
        sim_matrix = self.cosine_similarity_matrix(embeddings_a, embeddings_b)

        n, m = sim_matrix.shape
        matches = []

        for i in range(n):
            if i < sim_matrix.shape[0]:
                row = sim_matrix[i]
                max_sim = np.max(row)
                j = np.argmax(row)
                matches.append((i, j, float(max_sim)))

        matches.sort(key=lambda x: (-x[2], x[0]))

        used_a = set()
        used_b = set()
        final_matches = []

        for i, j, sim in matches:
            if i not in used_a and j not in used_b:
                final_matches.append((i, j, sim))
                used_a.add(i)
                used_b.add(j)

        final_matches.sort(key=lambda x: x[0])
        return final_matches
