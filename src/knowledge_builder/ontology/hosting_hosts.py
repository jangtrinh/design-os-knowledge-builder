"""Hosts that serve or mirror other publishers' work: their name says where a page lives, not who published it."""

HOSTING_HOSTS = (
    "web.archive.org", "raw.githubusercontent.com", "githubusercontent.com", "github.com", "arxiv.org", "hackmd.io",
)


def is_hosting_host(host):
    """True for a listed host or any subdomain of it (`gist.github.com`, `export.arxiv.org`); `github.io` is not listed."""
    return any(host == name or host.endswith("." + name) for name in HOSTING_HOSTS)
