"""Canonical denomination catalogue and default organisation templates for VINYRD.

These templates are operational defaults for onboarding and discovery. They are
not intended to redefine a church body's constitution. Denomination admins can
later rename, omit, or extend optional levels without changing member data.
"""

DENOMINATION_CATALOG = [
    {
        "value": "Catholic",
        "label": "Catholic (Roman Catholic)",
        "governance_model": "episcopal",
        "levels": [
            {"key": "ecclesiastical_province", "label": "Ecclesiastical Province / Archdiocese", "optional": True},
            {"key": "diocese", "label": "Diocese", "optional": False},
            {"key": "deanery", "label": "Deanery", "optional": True},
            {"key": "parish", "label": "Parish", "optional": False},
            {"key": "outstation", "label": "Outstation / Chaplaincy", "optional": True},
        ],
    },
    {
        "value": "Lutheran",
        "label": "Lutheran (ELCT / KKKT)",
        "governance_model": "synodical_episcopal",
        "levels": [
            {"key": "national_church", "label": "National Church", "optional": False},
            {"key": "diocese", "label": "Diocese / Mission Area", "optional": False},
            {"key": "district", "label": "District", "optional": True},
            {"key": "parish", "label": "Parish", "optional": False},
            {"key": "congregation", "label": "Congregation", "optional": False},
        ],
    },
    {
        "value": "Anglican",
        "label": "Anglican (ACT / KAT)",
        "governance_model": "episcopal",
        "levels": [
            {"key": "province", "label": "Province / National Church", "optional": False},
            {"key": "diocese", "label": "Diocese", "optional": False},
            {"key": "archdeaconry", "label": "Archdeaconry / Deanery", "optional": True},
            {"key": "parish", "label": "Parish", "optional": False},
            {"key": "local_church", "label": "Local Church / Chapelry", "optional": True},
        ],
    },
    {
        "value": "Moravian",
        "label": "Moravian",
        "governance_model": "synodical_episcopal",
        "levels": [
            {"key": "national_church", "label": "Moravian Church in Tanzania", "optional": False},
            {"key": "province", "label": "Province", "optional": False},
            {"key": "district", "label": "District", "optional": False},
            {"key": "ward", "label": "Ward / Parish", "optional": True},
            {"key": "congregation", "label": "Congregation", "optional": False},
            {"key": "sub_congregation", "label": "Sub-congregation", "optional": True},
        ],
    },
    {
        "value": "Africa Inland Church",
        "label": "Africa Inland Church Tanzania (AICT)",
        "governance_model": "episcopal",
        "levels": [
            {"key": "national_church", "label": "National Church", "optional": False},
            {"key": "diocese", "label": "Diocese", "optional": False},
            {"key": "pastorate", "label": "Pastorate", "optional": False},
            {"key": "local_congregation", "label": "Local Congregation", "optional": False},
        ],
    },
    {
        "value": "Baptist",
        "label": "Baptist",
        "governance_model": "congregational",
        "levels": [
            {"key": "convention", "label": "National Convention / Union", "optional": True},
            {"key": "association", "label": "Regional Association", "optional": True},
            {"key": "local_church", "label": "Local Church", "optional": False},
        ],
    },
    {
        "value": "Mennonite",
        "label": "Mennonite",
        "governance_model": "congregational_synodical",
        "levels": [
            {"key": "national_church", "label": "National Church / Conference", "optional": True},
            {"key": "region", "label": "Diocese / Region", "optional": True},
            {"key": "district", "label": "District / Area", "optional": True},
            {"key": "congregation", "label": "Congregation", "optional": False},
        ],
    },
    {
        "value": "Presbyterian",
        "label": "Presbyterian / Reformed",
        "governance_model": "presbyterian",
        "levels": [
            {"key": "general_assembly", "label": "General Assembly / National Church", "optional": True},
            {"key": "synod", "label": "Synod", "optional": True},
            {"key": "presbytery", "label": "Presbytery", "optional": False},
            {"key": "congregation", "label": "Congregation", "optional": False},
        ],
    },
    {
        "value": "Church of God",
        "label": "Church of God",
        "governance_model": "connectional",
        "levels": [
            {"key": "national_church", "label": "National Church", "optional": True},
            {"key": "region", "label": "Region / District", "optional": True},
            {"key": "local_church", "label": "Local Church", "optional": False},
        ],
    },
    {
        "value": "Bible Church",
        "label": "Bible Church",
        "governance_model": "congregational",
        "levels": [
            {"key": "national_fellowship", "label": "National Fellowship / Network", "optional": True},
            {"key": "region", "label": "Region / District", "optional": True},
            {"key": "local_church", "label": "Local Church", "optional": False},
        ],
    },
    {
        "value": "Evangelistic",
        "label": "Evangelistic Church",
        "governance_model": "connectional",
        "levels": [
            {"key": "national_church", "label": "National Church", "optional": True},
            {"key": "region", "label": "Region / District", "optional": True},
            {"key": "local_church", "label": "Local Church", "optional": False},
        ],
    },
    {
        "value": "Salvation Army",
        "label": "Salvation Army",
        "governance_model": "territorial",
        "levels": [
            {"key": "territory", "label": "Territory", "optional": False},
            {"key": "division", "label": "Division / District", "optional": True},
            {"key": "corps", "label": "Corps", "optional": False},
            {"key": "outpost", "label": "Outpost", "optional": True},
        ],
    },
    {
        "value": "Assemblies of God",
        "label": "Assemblies of God (TAG)",
        "governance_model": "connectional_pentecostal",
        "levels": [
            {"key": "national_church", "label": "National Church / General Council", "optional": False},
            {"key": "zone", "label": "Zone (Kanda)", "optional": False},
            {"key": "district", "label": "District (Jimbo)", "optional": False},
            {"key": "section", "label": "Section (Sehemu)", "optional": False},
            {"key": "local_church", "label": "Local Church", "optional": False},
        ],
    },
    {
        "value": "Seventh-day Adventist",
        "label": "Seventh-day Adventist",
        "governance_model": "representative",
        "levels": [
            {"key": "union", "label": "Union Conference / Union Mission", "optional": False},
            {"key": "conference", "label": "Conference / Field", "optional": False},
            {"key": "district", "label": "District", "optional": True},
            {"key": "local_church", "label": "Local Church / Company", "optional": False},
        ],
    },
    {
        "value": "New Apostolic",
        "label": "New Apostolic Church",
        "governance_model": "apostolic",
        "levels": [
            {"key": "district_apostle_area", "label": "District Apostle Area", "optional": False},
            {"key": "apostle_area", "label": "Apostle Area", "optional": True},
            {"key": "district", "label": "District", "optional": False},
            {"key": "congregation", "label": "Congregation", "optional": False},
        ],
    },
    {
        "value": "Pentecostal",
        "label": "Pentecostal / Charismatic",
        "governance_model": "configurable_pentecostal",
        "levels": [
            {"key": "national_church", "label": "National Church / Fellowship", "optional": True},
            {"key": "region", "label": "Region / Zone", "optional": True},
            {"key": "district", "label": "District / Section", "optional": True},
            {"key": "local_church", "label": "Local Church", "optional": False},
        ],
    },
    {
        "value": "Orthodox",
        "label": "Orthodox",
        "governance_model": "episcopal",
        "levels": [
            {"key": "patriarchate", "label": "Patriarchate / Church", "optional": True},
            {"key": "archdiocese", "label": "Archdiocese / Metropolis", "optional": False},
            {"key": "parish", "label": "Parish / Mission", "optional": False},
        ],
    },
    {
        "value": "Methodist",
        "label": "Methodist",
        "governance_model": "connectional",
        "levels": [
            {"key": "conference", "label": "Annual Conference / National Church", "optional": True},
            {"key": "district", "label": "District / Circuit", "optional": False},
            {"key": "local_church", "label": "Local Church / Society", "optional": False},
        ],
    },
    {
        "value": "Non-denominational",
        "label": "Non-denominational / Independent",
        "governance_model": "configurable",
        "levels": [
            {"key": "network", "label": "Network / Ministry", "optional": True},
            {"key": "campus", "label": "Campus / Branch", "optional": True},
            {"key": "local_church", "label": "Local Church", "optional": False},
        ],
    },
]


def denomination_catalog():
    # Return fresh dictionaries so callers cannot mutate process-global defaults.
    return [
        {
            **item,
            "levels": [dict(level) for level in item["levels"]],
        }
        for item in DENOMINATION_CATALOG
    ]
