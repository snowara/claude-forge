"""Verifier registry.

각 verifier는 개별 태스크에서 구현. 미구현 모듈은 ImportError로 건너뜀.
"""

VERIFIERS = {}

try:
    from .verify_blog import BlogVerifier
    VERIFIERS['blog-writer'] = BlogVerifier
except ImportError:
    pass

try:
    from .verify_daangn import DaangnVerifier
    VERIFIERS['daangn-biz'] = DaangnVerifier
except ImportError:
    pass

try:
    from .verify_finder import FinderVerifier
    VERIFIERS['product-finder'] = FinderVerifier
except ImportError:
    pass

try:
    from .verify_session import SessionVerifier
    VERIFIERS['session'] = SessionVerifier
except ImportError:
    pass

try:
    from .verify_advideo import AdVideoVerifier
    VERIFIERS['ad-video-crew'] = AdVideoVerifier
except ImportError:
    pass
