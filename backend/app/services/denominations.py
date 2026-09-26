"""Canonical denomination catalogue and default organisation templates for VINYRD.

Templates provide onboarding defaults only. They do not redefine a church body's
constitution. Organisation levels, office titles and permission suggestions can
be adapted by authorised denomination administrators.
"""


def position(title, permission_role="pastor_leader"):
    return {"title": title, "permission_role": permission_role}


def level(key, label, *positions, optional=False):
    return {
        "key": key,
        "label": label,
        "optional": optional,
        "positions": list(positions),
    }


DENOMINATION_CATALOG = [
    {
        "value": "Catholic",
        "label": "Catholic (Roman Catholic)",
        "governance_model": "episcopal",
        "levels": [
            level(
                "ecclesiastical_province",
                "Ecclesiastical Province / Archdiocese",
                position("Archbishop", "administrator"),
                position("Vicar General", "administrator"),
                position("Chancellor", "administrator"),
                position("Bursar / Treasurer", "accountant"),
                optional=True,
            ),
            level(
                "diocese",
                "Diocese",
                position("Bishop", "administrator"),
                position("Vicar General", "administrator"),
                position("Chancellor", "administrator"),
                position("Diocesan Bursar / Treasurer", "accountant"),
            ),
            level(
                "deanery",
                "Deanery",
                position("Dean", "pastor_leader"),
                optional=True,
            ),
            level(
                "parish",
                "Parish",
                position("Parish Priest", "pastor_leader"),
                position("Assistant Parish Priest", "pastor_leader"),
                position("Parish Secretary", "administrator"),
                position("Parish Treasurer", "accountant"),
            ),
            level(
                "outstation",
                "Outstation / Chaplaincy",
                position("Priest-in-Charge / Chaplain", "pastor_leader"),
                position("Catechist", "pastor_leader"),
                optional=True,
            ),
        ],
    },
    {
        "value": "Lutheran",
        "label": "Lutheran (ELCT / KKKT)",
        "governance_model": "synodical_episcopal",
        "levels": [
            level(
                "national_church",
                "National Church",
                position("Presiding Bishop / Head of Church", "administrator"),
                position("Secretary General", "administrator"),
                position("Treasurer / Finance Lead", "accountant"),
            ),
            level(
                "diocese",
                "Diocese / Mission Area",
                position("Diocesan Bishop", "administrator"),
                position("Diocesan General Secretary", "administrator"),
                position("Diocesan Treasurer", "accountant"),
            ),
            level(
                "district",
                "District",
                position("District Pastor / Dean", "pastor_leader"),
                position("District Secretary", "administrator"),
                optional=True,
            ),
            level(
                "parish",
                "Parish",
                position("Parish Pastor", "pastor_leader"),
                position("Assistant Pastor", "pastor_leader"),
                position("Parish Secretary", "administrator"),
                position("Parish Treasurer", "accountant"),
            ),
            level(
                "congregation",
                "Congregation",
                position("Congregation Pastor", "pastor_leader"),
                position("Congregation Chairperson", "administrator"),
                position("Congregation Treasurer", "accountant"),
            ),
        ],
    },
    {
        "value": "Anglican",
        "label": "Anglican (ACT / KAT)",
        "governance_model": "episcopal",
        "levels": [
            level(
                "province",
                "Province / National Church",
                position("Archbishop", "administrator"),
                position("Dean of the Province", "administrator"),
                position("General Secretary", "administrator"),
                position("Provincial Registrar", "administrator"),
                position("Treasurer", "accountant"),
            ),
            level(
                "diocese",
                "Diocese",
                position("Bishop", "administrator"),
                position("Diocesan Secretary", "administrator"),
                position("Diocesan Treasurer", "accountant"),
            ),
            level(
                "archdeaconry",
                "Archdeaconry / Deanery",
                position("Archdeacon / Dean", "pastor_leader"),
                optional=True,
            ),
            level(
                "parish",
                "Parish",
                position("Parish Priest / Rector", "pastor_leader"),
                position("Assistant Priest / Curate", "pastor_leader"),
                position("Parish Secretary", "administrator"),
                position("Parish Treasurer", "accountant"),
            ),
            level(
                "local_church",
                "Local Church / Chapelry",
                position("Priest-in-Charge", "pastor_leader"),
                position("Lay Leader", "pastor_leader"),
                optional=True,
            ),
        ],
    },
    {
        "value": "Moravian",
        "label": "Moravian",
        "governance_model": "synodical_episcopal",
        "levels": [
            level(
                "national_church",
                "Moravian Church in Tanzania",
                position("Presiding Bishop (Askofu Kiongozi)", "administrator"),
                position("Deputy Presiding Bishop", "administrator"),
                position("General Secretary (Katibu Mkuu)", "administrator"),
                position("General Treasurer (Mhazini Mkuu)", "accountant"),
            ),
            level(
                "province",
                "Province",
                position("Bishop / Provincial Chairperson", "administrator"),
                position("Provincial Secretary", "administrator"),
                position("Provincial Treasurer", "accountant"),
            ),
            level(
                "district",
                "District",
                position("District Chairperson / Pastor", "pastor_leader"),
                position("District Secretary", "administrator"),
            ),
            level(
                "ward",
                "Ward / Parish",
                position("Parish Pastor", "pastor_leader"),
                position("Parish Chairperson", "administrator"),
                optional=True,
            ),
            level(
                "congregation",
                "Congregation",
                position("Congregation Pastor", "pastor_leader"),
                position("Congregation Chairperson", "administrator"),
                position("Congregation Treasurer", "accountant"),
            ),
            level(
                "sub_congregation",
                "Sub-congregation",
                position("Pastor / Evangelist", "pastor_leader"),
                position("Local Chairperson", "administrator"),
                optional=True,
            ),
        ],
    },
    {
        "value": "Africa Inland Church",
        "label": "Africa Inland Church Tanzania (AICT)",
        "governance_model": "episcopal",
        "levels": [
            level(
                "national_church",
                "National Church",
                position("Archbishop", "administrator"),
                position("General Secretary", "administrator"),
                position("National Treasurer", "accountant"),
            ),
            level(
                "diocese",
                "Diocese",
                position("Bishop", "administrator"),
                position("Diocesan Secretary", "administrator"),
                position("Diocesan Treasurer", "accountant"),
            ),
            level(
                "pastorate",
                "Pastorate",
                position("Pastorate Pastor / Leader", "pastor_leader"),
                position("Pastorate Secretary", "administrator"),
            ),
            level(
                "local_congregation",
                "Local Congregation",
                position("Local Church Pastor", "pastor_leader"),
                position("Church Secretary", "administrator"),
                position("Church Treasurer", "accountant"),
            ),
        ],
    },
    {
        "value": "Baptist",
        "label": "Baptist",
        "governance_model": "congregational",
        "levels": [
            level(
                "convention",
                "National Convention / Union",
                position("President / Chairperson", "administrator"),
                position("General Secretary", "administrator"),
                position("Treasurer", "accountant"),
                optional=True,
            ),
            level(
                "association",
                "Regional Association",
                position("Moderator / Chairperson", "administrator"),
                position("Association Secretary", "administrator"),
                position("Treasurer", "accountant"),
                optional=True,
            ),
            level(
                "local_church",
                "Local Church",
                position("Senior Pastor / Pastor", "pastor_leader"),
                position("Church Secretary", "administrator"),
                position("Church Treasurer", "accountant"),
                position("Deacon / Elder", "pastor_leader"),
            ),
        ],
    },
    {
        "value": "Mennonite",
        "label": "Mennonite",
        "governance_model": "congregational_synodical",
        "levels": [
            level(
                "national_church",
                "National Church / Conference",
                position("Bishop / Conference Chairperson", "administrator"),
                position("General Secretary", "administrator"),
                position("Treasurer", "accountant"),
                optional=True,
            ),
            level(
                "region",
                "Diocese / Region",
                position("Bishop / Regional Chairperson", "administrator"),
                position("Regional Secretary", "administrator"),
                optional=True,
            ),
            level(
                "district",
                "District / Area",
                position("District Pastor / Chairperson", "pastor_leader"),
                optional=True,
            ),
            level(
                "congregation",
                "Congregation",
                position("Pastor", "pastor_leader"),
                position("Church Elder", "pastor_leader"),
                position("Secretary", "administrator"),
                position("Treasurer", "accountant"),
            ),
        ],
    },
    {
        "value": "Presbyterian",
        "label": "Presbyterian / Reformed",
        "governance_model": "presbyterian",
        "levels": [
            level(
                "general_assembly",
                "General Assembly / National Church",
                position("Moderator", "administrator"),
                position("General Secretary / Clerk", "administrator"),
                position("Treasurer", "accountant"),
                optional=True,
            ),
            level(
                "synod",
                "Synod",
                position("Synod Moderator", "administrator"),
                position("Synod Clerk", "administrator"),
                position("Treasurer", "accountant"),
                optional=True,
            ),
            level(
                "presbytery",
                "Presbytery",
                position("Presbytery Moderator", "administrator"),
                position("Presbytery Clerk", "administrator"),
                position("Treasurer", "accountant"),
            ),
            level(
                "congregation",
                "Congregation",
                position("Minister / Pastor", "pastor_leader"),
                position("Session Clerk", "administrator"),
                position("Elder", "pastor_leader"),
                position("Treasurer", "accountant"),
            ),
        ],
    },
    {
        "value": "Church of God",
        "label": "Church of God",
        "governance_model": "connectional",
        "levels": [
            level(
                "national_church",
                "National Church",
                position("National Overseer / Bishop", "administrator"),
                position("General Secretary", "administrator"),
                position("Treasurer", "accountant"),
                optional=True,
            ),
            level(
                "region",
                "Region / District",
                position("Regional / District Overseer", "administrator"),
                position("Secretary", "administrator"),
                optional=True,
            ),
            level(
                "local_church",
                "Local Church",
                position("Senior Pastor / Pastor", "pastor_leader"),
                position("Church Secretary", "administrator"),
                position("Treasurer", "accountant"),
            ),
        ],
    },
    {
        "value": "Bible Church",
        "label": "Bible Church",
        "governance_model": "congregational",
        "levels": [
            level(
                "national_fellowship",
                "National Fellowship / Network",
                position("National Leader / Chairperson", "administrator"),
                position("General Secretary", "administrator"),
                optional=True,
            ),
            level(
                "region",
                "Region / District",
                position("Regional Coordinator / Overseer", "administrator"),
                optional=True,
            ),
            level(
                "local_church",
                "Local Church",
                position("Senior Pastor / Pastor", "pastor_leader"),
                position("Elder", "pastor_leader"),
                position("Church Secretary", "administrator"),
                position("Treasurer", "accountant"),
            ),
        ],
    },
    {
        "value": "Evangelistic",
        "label": "Evangelistic Church",
        "governance_model": "connectional",
        "levels": [
            level(
                "national_church",
                "National Church",
                position("National Bishop / Overseer", "administrator"),
                position("General Secretary", "administrator"),
                position("Treasurer", "accountant"),
                optional=True,
            ),
            level(
                "region",
                "Region / District",
                position("Regional / District Overseer", "administrator"),
                position("Secretary", "administrator"),
                optional=True,
            ),
            level(
                "local_church",
                "Local Church",
                position("Senior Pastor / Pastor", "pastor_leader"),
                position("Church Secretary", "administrator"),
                position("Treasurer", "accountant"),
            ),
        ],
    },
    {
        "value": "Salvation Army",
        "label": "Salvation Army",
        "governance_model": "territorial",
        "levels": [
            level(
                "territory",
                "Territory",
                position("Territorial Commander", "administrator"),
                position("Chief Secretary", "administrator"),
                position("Finance Secretary", "accountant"),
            ),
            level(
                "division",
                "Division / District",
                position("Divisional / District Commander", "administrator"),
                position("Divisional Secretary", "administrator"),
                optional=True,
            ),
            level(
                "corps",
                "Corps",
                position("Corps Officer", "pastor_leader"),
                position("Corps Secretary", "administrator"),
                position("Corps Treasurer", "accountant"),
            ),
            level(
                "outpost",
                "Outpost",
                position("Outpost Officer / Leader", "pastor_leader"),
                optional=True,
            ),
        ],
    },
    {
        "value": "Assemblies of God",
        "label": "Assemblies of God (TAG)",
        "governance_model": "connectional_pentecostal",
        "levels": [
            level(
                "national_church",
                "National Church / General Council",
                position("Askofu Mkuu", "administrator"),
                position("Makamu Askofu Mkuu", "administrator"),
                position("Katibu Mkuu", "administrator"),
                position("Mtunza Hazina Mkuu", "accountant"),
            ),
            level(
                "zone",
                "Zone (Kanda)",
                position("Mwenyekiti wa Ushirika wa Kanda", "administrator"),
                position("Katibu / Mtunza Hazina wa Kanda", "accountant"),
            ),
            level(
                "district",
                "District (Jimbo)",
                position("Askofu", "administrator"),
                position("Makamu Askofu", "administrator"),
                position("Katibu", "administrator"),
                position("Mtunza Hazina", "accountant"),
            ),
            level(
                "section",
                "Section (Sehemu)",
                position("Mwangalizi", "pastor_leader"),
                position("Makamu Mwangalizi", "pastor_leader"),
                position("Katibu", "administrator"),
                position("Mtunza Hazina", "accountant"),
            ),
            level(
                "local_church",
                "Local Church",
                position("Mchungaji Kiongozi", "pastor_leader"),
                position("Mchungaji", "pastor_leader"),
                position("Katibu wa Kanisa", "administrator"),
                position("Mtunza Hazina", "accountant"),
            ),
        ],
    },
    {
        "value": "Seventh-day Adventist",
        "label": "Seventh-day Adventist",
        "governance_model": "representative",
        "levels": [
            level(
                "union",
                "Union Conference / Union Mission",
                position("President", "administrator"),
                position("Executive Secretary", "administrator"),
                position("Treasurer", "accountant"),
            ),
            level(
                "conference",
                "Conference / Field",
                position("President", "administrator"),
                position("Executive Secretary", "administrator"),
                position("Treasurer", "accountant"),
            ),
            level(
                "district",
                "District",
                position("District Pastor", "pastor_leader"),
                optional=True,
            ),
            level(
                "local_church",
                "Local Church / Company",
                position("Church Pastor", "pastor_leader"),
                position("First Elder / Elder", "pastor_leader"),
                position("Church Clerk", "administrator"),
                position("Church Treasurer", "accountant"),
            ),
        ],
    },
    {
        "value": "New Apostolic",
        "label": "New Apostolic Church",
        "governance_model": "apostolic",
        "levels": [
            level(
                "district_apostle_area",
                "District Apostle Area",
                position("District Apostle", "administrator"),
                position("District Apostle Helper", "administrator"),
            ),
            level(
                "apostle_area",
                "Apostle Area",
                position("Apostle", "administrator"),
                position("Bishop", "administrator"),
                optional=True,
            ),
            level(
                "district",
                "District",
                position("District Rector / District Elder", "pastor_leader"),
                position("District Evangelist", "pastor_leader"),
            ),
            level(
                "congregation",
                "Congregation",
                position("Rector", "pastor_leader"),
                position("Priest", "pastor_leader"),
                position("Deacon", "pastor_leader"),
            ),
        ],
    },
    {
        "value": "Pentecostal",
        "label": "Pentecostal / Charismatic",
        "governance_model": "configurable_pentecostal",
        "levels": [
            level(
                "national_church",
                "National Church / Fellowship",
                position("Presiding Bishop / General Overseer", "administrator"),
                position("General Secretary", "administrator"),
                position("Treasurer", "accountant"),
                optional=True,
            ),
            level(
                "region",
                "Region / Zone",
                position("Regional Bishop / Overseer", "administrator"),
                position("Regional Secretary", "administrator"),
                optional=True,
            ),
            level(
                "district",
                "District / Section",
                position("District / Section Overseer", "pastor_leader"),
                position("Secretary", "administrator"),
                optional=True,
            ),
            level(
                "local_church",
                "Local Church",
                position("Senior Pastor / Lead Pastor", "pastor_leader"),
                position("Associate Pastor", "pastor_leader"),
                position("Church Administrator / Secretary", "administrator"),
                position("Treasurer", "accountant"),
            ),
        ],
    },
    {
        "value": "Orthodox",
        "label": "Orthodox",
        "governance_model": "episcopal",
        "levels": [
            level(
                "patriarchate",
                "Patriarchate / Church",
                position("Patriarch / Primate", "administrator"),
                position("General Secretary", "administrator"),
                optional=True,
            ),
            level(
                "archdiocese",
                "Archdiocese / Metropolis",
                position("Archbishop / Metropolitan", "administrator"),
                position("Diocesan Secretary", "administrator"),
                position("Treasurer", "accountant"),
            ),
            level(
                "parish",
                "Parish / Mission",
                position("Parish Priest / Priest-in-Charge", "pastor_leader"),
                position("Deacon", "pastor_leader"),
                position("Parish Secretary", "administrator"),
                position("Treasurer", "accountant"),
            ),
        ],
    },
    {
        "value": "Methodist",
        "label": "Methodist",
        "governance_model": "connectional",
        "levels": [
            level(
                "conference",
                "Annual Conference / National Church",
                position("Presiding Bishop / Conference President", "administrator"),
                position("Conference Secretary", "administrator"),
                position("Treasurer", "accountant"),
                optional=True,
            ),
            level(
                "district",
                "District / Circuit",
                position("District Superintendent / Circuit Superintendent", "administrator"),
                position("Circuit Minister", "pastor_leader"),
            ),
            level(
                "local_church",
                "Local Church / Society",
                position("Minister / Pastor", "pastor_leader"),
                position("Lay Leader", "pastor_leader"),
                position("Church Secretary", "administrator"),
                position("Treasurer", "accountant"),
            ),
        ],
    },
    {
        "value": "Non-denominational",
        "label": "Non-denominational / Independent",
        "governance_model": "configurable",
        "levels": [
            level(
                "network",
                "Network / Ministry",
                position("Founder / Presiding Leader", "administrator"),
                position("Executive Director / Administrator", "administrator"),
                position("Finance Lead / Treasurer", "accountant"),
                optional=True,
            ),
            level(
                "campus",
                "Campus / Branch",
                position("Campus Pastor / Branch Pastor", "pastor_leader"),
                position("Campus Administrator", "administrator"),
                position("Finance Lead", "accountant"),
                optional=True,
            ),
            level(
                "local_church",
                "Local Church",
                position("Lead Pastor / Senior Pastor", "pastor_leader"),
                position("Associate Pastor", "pastor_leader"),
                position("Church Administrator / Secretary", "administrator"),
                position("Treasurer", "accountant"),
            ),
        ],
    },
]


def denomination_catalog():
    # Deep-copy nested levels and position records so API callers cannot mutate defaults.
    return [
        {
            **item,
            "levels": [
                {
                    **org_level,
                    "positions": [dict(position_item) for position_item in org_level["positions"]],
                }
                for org_level in item["levels"]
            ],
        }
        for item in DENOMINATION_CATALOG
    ]
