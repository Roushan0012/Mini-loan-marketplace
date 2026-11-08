from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

PURPOSE_ELIGIBILITY_MATCHING = "eligibility_matching"
PURPOSE_SHARING_WITH_MOCK_LENDERS = "sharing_with_mock_lenders"

SUPPORTED_PURPOSES: Set[str] = {
    PURPOSE_ELIGIBILITY_MATCHING,
    PURPOSE_SHARING_WITH_MOCK_LENDERS,
}


@dataclass(frozen=True)
class ConsentNotice:
    """Immutable versioned consent notice definition for fictional training workflows."""

    purpose: str
    title: str
    notice_version: str
    notice_text: str
    required_for_matching: bool


# Canonical notice registry preserving full historical notice versions
NOTICE_REGISTRY: Dict[Tuple[str, str], ConsentNotice] = {
    (PURPOSE_ELIGIBILITY_MATCHING, "v1.0"): ConsentNotice(
        purpose=PURPOSE_ELIGIBILITY_MATCHING,
        title="Illustrative Multi-Lender Eligibility Evaluation Consent",
        notice_version="v1.0",
        notice_text=(
            "The customer agrees that their fictional application information can be "
            "evaluated against three simulated lender policies to display illustrative "
            "eligibility results. "
            "TRAINING DEMO DISCLOSURE: No real lender is contacted. No real credit bureau "
            "is contacted. No real OTP gateway is used. No customer data is sent to external services. "
            "This notice text is purely for training demonstration purposes and does not represent "
            "actual legal consent wording."
        ),
        required_for_matching=True,
    ),
    (PURPOSE_SHARING_WITH_MOCK_LENDERS, "v1.0"): ConsentNotice(
        purpose=PURPOSE_SHARING_WITH_MOCK_LENDERS,
        title="Simulated Mock Lender Data Sharing Consent",
        notice_version="v1.0",
        notice_text=(
            "The customer agrees that fictional application information can be passed to "
            "local mock lender adapters to generate training offers. "
            "TRAINING DEMO DISCLOSURE: No real lender is contacted. No real credit bureau "
            "is contacted. No real OTP gateway is used. No customer data is sent to external services. "
            "This notice text is purely for training demonstration purposes and does not represent "
            "actual legal consent wording."
        ),
        required_for_matching=True,
    ),
}

# Current active notice version mapping per purpose
CURRENT_NOTICE_VERSIONS: Dict[str, str] = {
    PURPOSE_ELIGIBILITY_MATCHING: "v1.0",
    PURPOSE_SHARING_WITH_MOCK_LENDERS: "v1.0",
}


def get_current_notices() -> List[ConsentNotice]:
    """Retrieve the currently published notice for each supported consent purpose."""
    notices: List[ConsentNotice] = []
    for purpose in sorted(CURRENT_NOTICE_VERSIONS.keys()):
        version = CURRENT_NOTICE_VERSIONS[purpose]
        notice = NOTICE_REGISTRY.get((purpose, version))
        if notice:
            notices.append(notice)
    return notices


def get_notice(purpose: str, version: str) -> Optional[ConsentNotice]:
    """Retrieve a specific version of a consent notice from the registry."""
    return NOTICE_REGISTRY.get((purpose, version))


def is_valid_purpose(purpose: str) -> bool:
    """Check if the provided purpose string is a registered consent purpose."""
    return purpose in SUPPORTED_PURPOSES


def is_valid_purpose_and_version(purpose: str, version: str) -> bool:
    """Validate whether the given purpose and version exist in the immutable registry."""
    return (purpose, version) in NOTICE_REGISTRY


def is_current_version(purpose: str, version: str) -> bool:
    """Check whether the provided version is the currently published active version."""
    return CURRENT_NOTICE_VERSIONS.get(purpose) == version


def get_current_version(purpose: str) -> Optional[str]:
    """Return the current active version string for a purpose."""
    return CURRENT_NOTICE_VERSIONS.get(purpose)


def get_required_purposes() -> Set[str]:
    """Return the set of purposes required for matching readiness."""
    return {
        notice.purpose
        for notice in get_current_notices()
        if notice.required_for_matching
    }
