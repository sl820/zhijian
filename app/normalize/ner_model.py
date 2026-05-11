"""
NER (Named Entity Recognition) model for Chinese text using BERT.
"""

import logging
import torch
from transformers import BertTokenizer, BertForTokenClassification

logger = logging.getLogger(__name__)

NER_LABELS = ["O", "B-PER", "I-PER", "B-LOC", "I-LOC", "B-TIME", "I-TIME", "B-ORG", "I-ORG", "B-WORK", "I-WORK"]

LABEL_TO_ID = {label: idx for idx, label in enumerate(NER_LABELS)}
ID_TO_LABEL = {idx: label for idx, label in enumerate(NER_LABELS)}


class NERModel:
    """
    Named Entity Recognition model using BERT for Chinese text.
    """

    def __init__(self, model_path: str = None, device: str = None):
        """
        Initialize the NER model.

        Args:
            model_path: Path to a fine-tuned model. If None, uses "bert-base-chinese".
            device: Device to run the model on. If None, uses CUDA if available, else CPU.
        """
        self.model_path = model_path or "bert-base-chinese"
        # Force CPU for RTX 50xx series compatibility issues
        # torch.cuda.is_available() returns True but actual kernels fail
        self.device = "cpu"
        self.tokenizer = None
        self.model = None
        self._loaded = False
        logger.info(f"NERModel initialized with model_path={self.model_path}, device={self.device}")

    def _load_model(self):
        """Lazy load the model and tokenizer."""
        if self._loaded:
            return

        logger.info(f"Loading NER model from {self.model_path}...")
        self.tokenizer = BertTokenizer.from_pretrained(self.model_path)

        num_labels = len(NER_LABELS)
        self.model = BertForTokenClassification.from_pretrained(
            self.model_path,
            num_labels=num_labels
        )
        self.model.to(self.device)
        self.model.eval()
        self._loaded = True
        logger.info("NER model loaded successfully")

    def load_ner_model(self):
        """
        Public method to explicitly load the NER model.
        Alias for _load_model() for compatibility.
        """
        self._load_model()

    def predict(self, text: str) -> list:
        """
        Predict named entities in a single text.

        Args:
            text: Input text string.

        Returns:
            List of dictionaries, each containing 'type', 'name', 'start', and 'end'.
            Example: [{"type": "PER", "name": "张三", "start": 0, "end": 2}, ...]
        """
        self._load_model()

        if not text:
            return []

        # Tokenize the text
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=512
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        # Get predictions
        with torch.no_grad():
            outputs = self.model(**inputs)
            predictions = torch.argmax(outputs.logits, dim=-1)

        # Decode predictions to entities
        tokens = self.tokenizer.convert_ids_to_tokens(inputs["input_ids"][0])
        predictions = predictions[0].cpu().tolist()

        entities = []
        current_entity = None

        for i, (token, pred_id) in enumerate(zip(tokens, predictions)):
            if token in ["[CLS]", "[SEP]", "[PAD]"]:
                continue

            label = ID_TO_LABEL.get(pred_id, "O")

            if label.startswith("B-"):
                # Save previous entity if exists
                if current_entity is not None:
                    entities.append(current_entity)

                # Start new entity
                entity_type = label[2:]
                # Find the actual character position in original text
                token_text = token.replace("##", "")
                start_pos = text.find(token_text)
                if start_pos == -1:
                    start_pos = 0

                current_entity = {
                    "type": entity_type,
                    "name": token_text,
                    "start": start_pos,
                    "end": start_pos + len(token_text)
                }

            elif label.startswith("I-") and current_entity is not None:
                # Continue current entity
                entity_type = label[2:]
                if entity_type == current_entity["type"]:
                    token_text = token.replace("##", "")
                    current_entity["name"] += token_text
                    current_entity["end"] = current_entity["start"] + len(current_entity["name"])
                else:
                    # I-tag doesn't match B-tag, save current and start new if needed
                    entities.append(current_entity)
                    current_entity = None

            else:
                # O tag or I-tag without valid B-tag
                if current_entity is not None:
                    entities.append(current_entity)
                    current_entity = None

        # Don't forget the last entity
        if current_entity is not None:
            entities.append(current_entity)

        logger.debug(f"Predicted {len(entities)} entities in text: {entities}")
        return entities

    def batch_predict(self, texts: list) -> list:
        """
        Predict named entities in a batch of texts.

        Args:
            texts: List of input text strings.

        Returns:
            List of lists of entity dictionaries, one list per input text.
        """
        self._load_model()
        return [self.predict(text) for text in texts]
