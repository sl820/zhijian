"""
Text deduplication using MinHash and SimHash algorithms.

This module provides functionality for detecting duplicate or near-duplicate text
documents using locality-sensitive hashing techniques.
"""

import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)


class TextHasher:
    """Computes text fingerprints using MinHash and SimHash algorithms."""

    def minhash(self, text: str, num_hashes: int = 128) -> List[int]:
        """
        Compute MinHash signature for text using character trigrams as shingles.

        Args:
            text: Input text to hash.
            num_hashes: Number of hash functions to use (signature length).

        Returns:
            List of minhash values forming the signature.
        """
        shingles = self._create_shingles(text, k=3)
        if not shingles:
            return [0] * num_hashes

        signature = []
        for seed in range(num_hashes):
            min_hash = float('inf')
            for shingle in shingles:
                hash_val = hash((seed, shingle))
                if hash_val < min_hash:
                    min_hash = hash_val
            signature.append(min_hash if min_hash != float('inf') else 0)

        return signature

    def simhash(self, text: str, num_bits: int = 64) -> int:
        """
        Compute SimHash fingerprint for text using character bigrams as features.

        Args:
            text: Input text to hash.
            num_bits: Number of bits in the fingerprint (default 64).

        Returns:
            64-bit integer fingerprint.
        """
        features = self._create_shingles(text, k=2)
        if not features:
            return 0

        v = [0] * num_bits

        for shingle in features:
            hash_val = hash(shingle)
            for i in range(num_bits):
                bit = (hash_val >> i) & 1
                if bit:
                    v[i] += 1
                else:
                    v[i] -= 1

        fingerprint = 0
        for i in range(num_bits):
            if v[i] > 0:
                fingerprint |= (1 << i)

        return fingerprint

    def compute_similarity(self, hash1, hash2) -> float:
        """
        Compute similarity between two hash signatures.

        Args:
            hash1: First hash (list for MinHash, int for SimHash).
            hash2: Second hash (list for MinHash, int for SimHash).

        Returns:
            Similarity score between 0.0 and 1.0.
        """
        if isinstance(hash1, list) and isinstance(hash2, list):
            return self._minhash_similarity(hash1, hash2)
        elif isinstance(hash1, int) and isinstance(hash2, int):
            return self._simhash_similarity(hash1, hash2)
        else:
            raise TypeError("Hashes must be both lists (MinHash) or both ints (SimHash)")

    def _create_shingles(self, text: str, k: int = 3) -> List[str]:
        """
        Create k-character shingles from text.

        Args:
            text: Input text.
            k: Shingle size (number of characters).

        Returns:
            List of shingles as strings.
        """
        if not text or k <= 0:
            return []

        shingles = []
        for i in range(len(text) - k + 1):
            shingles.append(text[i:i + k])
        return shingles

    def _minhash_similarity(self, sig1: List[int], sig2: List[int]) -> float:
        """
        Compute Jaccard similarity between two MinHash signatures.

        Args:
            sig1: First signature.
            sig2: Second signature.

        Returns:
            Jaccard similarity (fraction of matching positions).
        """
        if len(sig1) != len(sig2):
            raise ValueError("Signatures must have the same length")

        if len(sig1) == 0:
            return 0.0

        matches = sum(1 for a, b in zip(sig1, sig2) if a == b)
        return matches / len(sig1)

    def _simhash_similarity(self, fp1: int, fp2: int) -> float:
        """
        Compute similarity between two SimHash fingerprints using Hamming distance.

        Args:
            fp1: First fingerprint.
            fp2: Second fingerprint.

        Returns:
            Similarity based on Hamming distance (1 - hamming_distance / 64).
        """
        xor = fp1 ^ fp2
        hamming_distance = bin(xor).count('1')
        return 1.0 - (hamming_distance / 64.0)


class Deduplicator:
    """Identifies and removes duplicate texts using MinHash or SimHash."""

    def __init__(self, threshold: float = 0.85, method: str = 'minhash'):
        """
        Initialize the deduplicator.

        Args:
            threshold: Similarity threshold above which texts are considered duplicates.
            method: Hashing method to use ('minhash' or 'simhash').

        Raises:
            ValueError: If method is not 'minhash' or 'simhash'.
        """
        if method not in ('minhash', 'simhash'):
            raise ValueError(f"Method must be 'minhash' or 'simhash', got '{method}'")
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(f"Threshold must be between 0.0 and 1.0, got {threshold}")

        self.threshold = threshold
        self.method = method
        self.hasher = TextHasher()
        logger.info(f"Initialized Deduplicator with method={method}, threshold={threshold}")

    def find_duplicates(self, texts: List[str]) -> List[Tuple[int, int, float]]:
        """
        Find all pairs of duplicate texts above the similarity threshold.

        Args:
            texts: List of text strings to check for duplicates.

        Returns:
            List of tuples (index_i, index_j, similarity) for duplicate pairs.
            Only returns pairs where i < j.
        """
        if not texts:
            return []

        logger.info(f"Computing hashes for {len(texts)} texts using {self.method}")
        hashes = self._compute_hashes(texts)

        duplicates = []
        for i in range(len(texts)):
            for j in range(i + 1, len(texts)):
                similarity = self.hasher.compute_similarity(hashes[i], hashes[j])
                if similarity >= self.threshold:
                    duplicates.append((i, j, similarity))
                    logger.debug(f"Found duplicate: ({i}, {j}) similarity={similarity:.4f}")

        logger.info(f"Found {len(duplicates)} duplicate pairs")
        return duplicates

    def cluster_documents(self, texts: List[str]) -> List[List[int]]:
        """
        Group texts into clusters of duplicates using union-find.

        Args:
            texts: List of text strings to cluster.

        Returns:
            List of clusters, where each cluster is a list of text indices.
            Documents that are not duplicates of any other document form singleton clusters.
        """
        if not texts:
            return []

        n = len(texts)
        parent = list(range(n))
        rank = [0] * n

        def find(x: int) -> int:
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]

        def union(x: int, y: int):
            px, py = find(x), find(y)
            if px == py:
                return
            if rank[px] < rank[py]:
                px, py = py, px
            parent[py] = px
            if rank[px] == rank[py]:
                rank[px] += 1

        duplicates = self.find_duplicates(texts)
        for i, j, _ in duplicates:
            union(i, j)

        clusters = {}
        for idx in range(n):
            root = find(idx)
            if root not in clusters:
                clusters[root] = []
            clusters[root].append(idx)

        result = list(clusters.values())
        logger.info(f"Formed {len(result)} clusters from {n} documents")
        return result

    def deduplicate(self, texts: List[str], prefer_longer: bool = True) -> List[str]:
        """
        Remove duplicate texts, keeping one representative per cluster.

        Args:
            texts: List of text strings to deduplicate.
            prefer_longer: If True, keep the longest text in each cluster.
                           If False, keep the first occurrence.

        Returns:
            List of unique texts with duplicates removed.
        """
        if not texts:
            return []

        clusters = self.cluster_documents(texts)
        unique_indices = []

        for cluster in clusters:
            if prefer_longer:
                representative = max(cluster, key=lambda idx: len(texts[idx]))
            else:
                representative = cluster[0]
            unique_indices.append(representative)

        unique_indices.sort()
        result = [texts[idx] for idx in unique_indices]
        logger.info(f"Deduplicated {len(texts)} texts to {len(result)} unique texts")
        return result

    def _compute_hashes(self, texts: List[str]) -> List:
        """
        Compute hashes for all texts using the configured method.

        Args:
            texts: List of text strings.

        Returns:
            List of hash signatures (lists for MinHash, ints for SimHash).
        """
        hashes = []
        for text in texts:
            if self.method == 'minhash':
                hashes.append(self.hasher.minhash(text))
            else:
                hashes.append(self.hasher.simhash(text))
        return hashes
