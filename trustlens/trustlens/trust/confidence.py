"""FLOW-10: Categorical confidence calibration."""
from typing import Literal

def confidence_band(score: float) -> Literal["High", "Medium", "Low", "Unverified"]:
    """Map raw model classification probability to categorical confidence band.
    
    Prevents deceptive display of raw model probabilities as calibrated ground-truth truthfulness.
    """
    if score >= 0.85:
        return "High"
    elif score >= 0.60:
        return "Medium"
    elif score >= 0.35:
        return "Low"
    else:
        return "Unverified"
