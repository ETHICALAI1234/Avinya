import os
from pathlib import Path
from dotenv import load_dotenv

# Locate and load .env
base_dir = Path(__file__).resolve().parent.parent
env_path = base_dir / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

class Settings:
    BASE_DIR: Path = base_dir
    CONFIG_DIR: Path = base_dir / "config"
    DATA_DIR: Path = base_dir / "data"

    MODE: str = os.getenv("TRUSTLENS_MODE", "grounded")
    GROUNDED_MODEL: str = os.getenv("TRUSTLENS_GROUNDED_MODEL", "KRLabsOrg/lettucedect-base-modernbert-en-v1")
    NLI_MODEL: str = os.getenv("TRUSTLENS_NLI_MODEL", "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7")
    HHEM_MODEL: str = os.getenv("TRUSTLENS_HHEM_MODEL", "vectara/hallucination_evaluation_model")
    DEVICE: str = os.getenv("TRUSTLENS_DEVICE", "cpu")
    
    OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
    ANTHROPIC_API_KEY: str | None = os.getenv("ANTHROPIC_API_KEY")
    GROQ_API_KEY: str | None = os.getenv("GROQ_API_KEY")
    GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    GOOGLE_API_KEY: str | None = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    TAVILY_API_KEY: str | None = os.getenv("TAVILY_API_KEY")
    UPSTREAM_MODEL: str = os.getenv("TRUSTLENS_UPSTREAM_MODEL", "gemini/gemini-2.5-flash")


    # Thresholds
    SPAN_CONFIDENCE_MIN: float = float(os.getenv("TRUSTLENS_SPAN_CONFIDENCE_MIN", "0.50"))
    ENTAILMENT_MIN: float = float(os.getenv("TRUSTLENS_ENTAILMENT_MIN", "0.60"))
    TRUST_HIGH: float = float(os.getenv("TRUSTLENS_TRUST_HIGH", "0.80"))
    TRUST_LOW: float = float(os.getenv("TRUSTLENS_TRUST_LOW", "0.50"))

    # Timeouts & Limits
    MAX_EVIDENCE_PER_CLAIM: int = int(os.getenv("TRUSTLENS_MAX_EVIDENCE", "4"))
    REQUEST_TIMEOUT_SECONDS: float = float(os.getenv("TRUSTLENS_TIMEOUT", "60.0"))

settings = Settings()
