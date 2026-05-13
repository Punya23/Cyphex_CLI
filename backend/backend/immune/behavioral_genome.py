"""
CYPHEX — Behavioral Genome (Blue Team Defense)

Per-endpoint anomaly detector using Isolation Forest.
Learns what "normal" looks like for each endpoint, then scores
incoming requests — anything abnormal gets flagged.

This is the "immune system" core: it doesn't need a database of attacks,
it just knows what YOUR app looks like and blocks everything else.

Dependencies: scikit-learn, numpy (both CPU-only, work on Pi 5)
"""

import math
import json
import os
from collections import Counter
from datetime import datetime
from typing import Optional

import numpy as np

try:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    import joblib
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

from models.genome import EndpointProfile, GenomeState
from models.scan import ScanContext


class BehavioralGenome:
    """
    Blue Team Defense — learns what "normal" looks like for each endpoint
    and scores incoming requests for anomaly.

    Uses scikit-learn Isolation Forest:
    - Lightweight (<1ms inference, CPU-only)
    - Unsupervised (no labeled data needed)
    - Works on Raspberry Pi 5
    """

    def __init__(self):
        self.endpoint_models: dict[str, IsolationForest] = {}
        self.endpoint_profiles: dict[str, EndpointProfile] = {}
        self.scalers: dict[str, StandardScaler] = {}
        self.state: Optional[GenomeState] = None
        # Accumulate attack samples across generations for better learning
        self._attack_history: dict[str, list[np.ndarray]] = {}

    def build_from_scan(self, context: ScanContext) -> GenomeState:
        """
        Build initial genome from a CYPHEX scan result.
        Uses data already collected by Agent 01 (Recon) and Agent 02 (Crawler).
        """
        self.state = GenomeState(target_url=context.target_url)

        # Profile each endpoint discovered by the crawler
        for endpoint in context.all_endpoints:
            profile = self._build_endpoint_profile(endpoint, context)
            key = self._endpoint_key(endpoint)
            self.endpoint_profiles[key] = profile
            self.state.endpoints[key] = profile

            # Generate synthetic "normal" samples and train Isolation Forest
            normal_samples = self._generate_normal_samples(profile, n=100)
            if len(normal_samples) > 10:
                self._train_endpoint_model(key, normal_samples)

        # Profile forms as well
        for form in context.all_forms:
            profile = EndpointProfile(
                endpoint=form.action,
                method=form.method.upper(),
                input_fields=form.inputs,
                input_length_mean=15.0,
                input_length_std=10.0,
                input_charset_expected="mixed",
                input_entropy_mean=3.2,
                input_entropy_std=0.5,
                sample_count=100,
            )
            key = self._endpoint_key(form.action)
            self.endpoint_profiles[key] = profile
            self.state.endpoints[key] = profile

            normal_samples = self._generate_normal_samples(profile, n=100)
            if len(normal_samples) > 10:
                self._train_endpoint_model(key, normal_samples)

        return self.state

    def extract_features(self, text: str) -> np.ndarray:
        """
        Extract 9-dimensional feature vector from an input string.

        Features:
        1. input_length
        2. entropy (Shannon entropy)
        3. special_char_ratio (non-alphanumeric %)
        4. url_encoding_ratio (% of %XX sequences)
        5. uppercase_ratio
        6. digit_ratio
        7. max_token_length (longest "word")
        8. sql_keyword_score (presence of SQL/JS keywords)
        9. sqli_pattern_score (regex pattern matching for injection syntax)
        """
        if not text:
            return np.zeros(9)

        length = len(text)
        entropy = self._shannon_entropy(text)

        # Special character ratio
        special = sum(1 for c in text if not c.isalnum() and c not in " ._-")
        special_ratio = special / max(length, 1)

        # URL encoding ratio
        import re
        url_encoded = len(re.findall(r'%[0-9A-Fa-f]{2}', text))
        url_ratio = url_encoded * 3 / max(length, 1)  # Each %XX is 3 chars

        # Uppercase ratio
        upper = sum(1 for c in text if c.isupper())
        upper_ratio = upper / max(length, 1)

        # Digit ratio
        digits = sum(1 for c in text if c.isdigit())
        digit_ratio = digits / max(length, 1)

        # Max token length
        tokens = re.split(r'[\s+\-=&?/]', text)
        max_token = max((len(t) for t in tokens if t), default=0)

        # SQL/JS keyword score (expanded list)
        keywords = [
            'select', 'union', 'insert', 'update', 'delete', 'drop', 'exec',
            'script', 'alert', 'onerror', 'onload', 'eval', 'document',
            'window', 'cookie', '--', '/*', '*/', 'waitfor', 'sleep',
            'benchmark', 'char(', 'concat(', 'information_schema',
            'onclick', 'onfocus', 'onmouseover', 'src=', 'href=',
            'passwd', 'shadow', '/etc/', 'cmd.exe', 'powershell',
            'wget', 'curl', 'base64', 'fromcharcode', 'settimeout',
        ]
        text_lower = text.lower()
        keyword_hits = sum(1 for kw in keywords if kw in text_lower)
        keyword_score = min(keyword_hits / 2.0, 1.0)  # More aggressive: /2 instead of /3

        # SQLi/XSS pattern matching (regex-based, catches structural attacks)
        sqli_patterns = [
            r"'\s*(or|and)\s+.*[=<>]",      # ' OR 1=1, ' AND 1=1
            r"'\s*;\s*(drop|delete|insert|update)",  # '; DROP TABLE
            r"\d+\s*=\s*\d+",               # 1=1, 2=2 (tautology)
            r"'\s*=\s*'",                   # ''=''
            r"union\s+(all\s+)?select",      # UNION SELECT
            r"order\s+by\s+\d+",            # ORDER BY 10
            r"(;|\|\||&&)\s*(ls|cat|dir|whoami|id|ping|curl|wget)",  # CMDi
            r"<\s*script[^>]*>",             # <script>
            r"<\s*\w+[^>]+on\w+\s*=",        # <tag onerror=, <img onload=
            r"<\s*(img|svg|body|iframe|input|details|marquee|object)",  # HTML injection tags
            r"javascript\s*:",               # javascript: URI
            r"\$\(|`[^`]+`",                # $(cmd) or `cmd` (shell)
        ]
        pattern_hits = sum(
            1 for p in sqli_patterns
            if re.search(p, text_lower)
        )
        sqli_pattern_score = min(pattern_hits / 2.0, 1.0)

        return np.array([
            length,
            entropy,
            special_ratio,
            url_ratio,
            upper_ratio,
            digit_ratio,
            max_token,
            keyword_score,
            sqli_pattern_score,
        ])

    def score_request(self, endpoint: str, payload: str) -> float:
        """
        Score a request for anomaly. Returns 0.0 (normal) to 1.0 (anomalous).

        COMBINED scoring:
        - ML score (Isolation Forest): catches statistical anomalies
        - Heuristic score: catches known attack patterns (keywords, encoding)
        - Final = weighted combination for maximum detection
        """
        key = self._endpoint_key(endpoint)

        # Extract features
        features = self.extract_features(payload).reshape(1, -1)

        # Heuristic score (always available, catches obvious attacks)
        heuristic = self._heuristic_score(features[0])

        # ML score (if model is trained for this endpoint)
        ml_score = 0.0
        if key in self.endpoint_models and key in self.scalers:
            try:
                scaled = self.scalers[key].transform(features)
                raw_score = self.endpoint_models[key].decision_function(scaled)[0]
                # Convert: lower raw_score = more anomalous
                # Typical range is [-0.5, 0.5], map to [1.0, 0.0]
                ml_score = max(0.0, min(1.0, 0.5 - raw_score))
            except Exception:
                ml_score = 0.0

        # Combined score: take the MAX of both signals
        # This means if EITHER detector flags it, it's suspicious
        # The heuristic catches keyword-based attacks
        # The ML catches statistical anomalies (unusual patterns)
        combined = max(ml_score, heuristic)

        # Boost: if BOTH detectors agree it's suspicious, extra confidence
        if ml_score > 0.3 and heuristic > 0.3:
            combined = min(1.0, combined + 0.15)

        return combined

    def retrain(self, endpoint: str, attack_samples: list[str]):
        """
        Retrain the genome for a specific endpoint with attack data.
        Called after each evolution generation.

        ACCUMULATES attack history across generations so the genome
        gets progressively better — each generation's bypasses make
        the next generation's detection stronger.
        """
        key = self._endpoint_key(endpoint)

        # Get existing normal samples or generate them
        profile = self.endpoint_profiles.get(key)
        if not profile:
            return

        # Generate diverse normal samples (different seed each time)
        seed = hash(datetime.now().isoformat()) % (2**31)
        normal_samples = self._generate_normal_samples(profile, n=200, seed=seed)

        # Extract features from new attack samples
        new_attack_features = [self.extract_features(s) for s in attack_samples]

        # ACCUMULATE attacks across generations (key improvement)
        if key not in self._attack_history:
            self._attack_history[key] = []
        self._attack_history[key].extend(new_attack_features)

        # Use ALL accumulated attacks for training (up to 500)
        all_attacks = self._attack_history[key][-500:]

        # Combine: mostly normal + accumulated attacks
        all_features = normal_samples + all_attacks
        contamination = len(all_attacks) / max(len(all_features), 1)
        self._train_endpoint_model(key, all_features, contamination=contamination)

        if self.state:
            self.state.last_evolved = datetime.now().isoformat()

    def _train_endpoint_model(
        self, key: str, samples: list[np.ndarray], contamination: float = 0.1
    ):
        """Train an Isolation Forest for a specific endpoint."""
        if not HAS_SKLEARN or len(samples) < 10:
            return

        X = np.array(samples)

        # Scale features
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # Train Isolation Forest
        clf = IsolationForest(
            n_estimators=100,
            contamination=max(0.01, min(contamination, 0.4)),
            random_state=42,
            n_jobs=1,  # Single thread for Pi 5 compatibility
        )
        clf.fit(X_scaled)

        self.endpoint_models[key] = clf
        self.scalers[key] = scaler

    def _build_endpoint_profile(
        self, endpoint: str, context: ScanContext
    ) -> EndpointProfile:
        """Build a behavioral profile from scan context data."""
        # Determine method from discovered params/forms
        method = "GET"
        input_fields = []

        for param in context.all_params:
            if param.url == endpoint:
                input_fields.append(param.name)

        for form in context.all_forms:
            if form.action == endpoint:
                method = form.method.upper()
                input_fields = form.inputs

        return EndpointProfile(
            endpoint=endpoint,
            method=method,
            input_fields=input_fields,
            input_length_mean=12.0,
            input_length_std=8.0,
            input_charset_expected="alphanumeric",
            input_entropy_mean=3.0,
            input_entropy_std=0.4,
            sample_count=100,
        )

    def _generate_normal_samples(
        self, profile: EndpointProfile, n: int = 100, seed: int = 42
    ) -> list[np.ndarray]:
        """
        Generate synthetic "normal" traffic samples for an endpoint.
        These represent typical user inputs (search queries, form data, etc.)
        Uses different seeds each time for diversity.
        """
        samples = []
        rng = np.random.default_rng(seed)

        for _ in range(n):
            # Simulate normal input with varied patterns
            length = max(1, int(rng.normal(profile.input_length_mean, profile.input_length_std)))
            chars = 'abcdefghijklmnopqrstuvwxyz0123456789 '
            text = ''.join(rng.choice(list(chars)) for _ in range(length))
            features = self.extract_features(text)
            samples.append(features)

        return samples

    def _heuristic_score(self, features: np.ndarray) -> float:
        """
        Heuristic scoring based on feature thresholds.
        Catches attacks that Isolation Forest may miss.
        """
        score = 0.0

        length = features[0]
        entropy = features[1]
        special_ratio = features[2]
        url_ratio = features[3]
        keyword_score = features[7]
        sqli_pattern = features[8] if len(features) > 8 else 0.0

        # Very long inputs are suspicious
        if length > 100:
            score += 0.2
        if length > 500:
            score += 0.3

        # High entropy = random/encoded = suspicious
        if entropy > 4.0:
            score += 0.2
        if entropy > 5.0:
            score += 0.3

        # Lots of special characters = suspicious
        if special_ratio > 0.3:
            score += 0.2
        if special_ratio > 0.15:
            score += 0.1

        # URL encoding = possible evasion
        if url_ratio > 0.1:
            score += 0.15

        # SQL/JS keywords
        if keyword_score > 0.2:
            score += 0.3
        if keyword_score > 0.5:
            score += 0.2

        # SQLi/XSS PATTERN match (strongest signal!)
        # Even one regex pattern hit = almost certainly an attack
        if sqli_pattern > 0.0:
            score += 0.5
        if sqli_pattern > 0.5:
            score += 0.3

        return min(score, 1.0)

    def _shannon_entropy(self, text: str) -> float:
        """Shannon entropy — measures randomness of input."""
        if not text:
            return 0.0
        freq = Counter(text)
        length = len(text)
        return -sum(
            (count / length) * math.log2(count / length)
            for count in freq.values()
        )

    def _endpoint_key(self, endpoint: str) -> str:
        """Normalize endpoint to a consistent key."""
        return endpoint.rstrip("/").lower()

    def save(self, filepath: str):
        """Serialize genome to disk."""
        if not HAS_SKLEARN:
            return
        data = {
            "state": self.state.to_dict() if self.state else {},
            "profiles": {k: v.to_dict() for k, v in self.endpoint_profiles.items()},
        }
        # Save metadata as JSON
        with open(filepath + ".json", "w") as f:
            json.dump(data, f, indent=2)
        # Save sklearn models
        models_data = {
            "models": self.endpoint_models,
            "scalers": self.scalers,
        }
        joblib.dump(models_data, filepath + ".pkl")

    @classmethod
    def load(cls, filepath: str) -> "BehavioralGenome":
        """Load genome from disk."""
        genome = cls()
        if os.path.exists(filepath + ".pkl"):
            models_data = joblib.load(filepath + ".pkl")
            genome.endpoint_models = models_data.get("models", {})
            genome.scalers = models_data.get("scalers", {})
        return genome
