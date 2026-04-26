"""
URL Registry — Versioned allowlist of all source URLs.

Each entry carries metadata used downstream by the scraping service,
chunker, and embedding pipeline. Only URLs listed here are fetched;
the system never crawls beyond this registry.
"""

URL_REGISTRY = [
    {
        "url": "https://groww.in/mutual-funds/parag-parikh-long-term-value-fund-direct-growth",
        "source_type": "groww_scheme_page",
        "scheme_name": "Parag Parikh Flexi Cap Fund",
        "scheme_id": "ppfas_flexi_cap",
        "amc": "PPFAS Mutual Fund",
        "category": "equity",
        "sub_category": "flexi_cap",
    },
    {
        "url": "https://groww.in/mutual-funds/parag-parikh-large-cap-fund-direct-growth",
        "source_type": "groww_scheme_page",
        "scheme_name": "Parag Parikh Large Cap Fund",
        "scheme_id": "ppfas_large_cap",
        "amc": "PPFAS Mutual Fund",
        "category": "equity",
        "sub_category": "large_cap",
    },
    {
        "url": "https://groww.in/mutual-funds/parag-parikh-elss-tax-saver-fund-direct-growth",
        "source_type": "groww_scheme_page",
        "scheme_name": "Parag Parikh ELSS Tax Saver Fund",
        "scheme_id": "ppfas_elss",
        "amc": "PPFAS Mutual Fund",
        "category": "equity",
        "sub_category": "elss",
    },
    {
        "url": "https://groww.in/mutual-funds/parag-parikh-conservative-hybrid-fund-direct-growth",
        "source_type": "groww_scheme_page",
        "scheme_name": "Parag Parikh Conservative Hybrid Fund",
        "scheme_id": "ppfas_conservative_hybrid",
        "amc": "PPFAS Mutual Fund",
        "category": "hybrid",
        "sub_category": "conservative_hybrid",
    },
    {
        "url": "https://groww.in/mutual-funds/parag-parikh-arbitrage-fund-direct-growth",
        "source_type": "groww_scheme_page",
        "scheme_name": "Parag Parikh Arbitrage Fund",
        "scheme_id": "ppfas_arbitrage",
        "amc": "PPFAS Mutual Fund",
        "category": "hybrid",
        "sub_category": "arbitrage",
    },
]
