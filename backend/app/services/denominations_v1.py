"""Canonical denomination catalogue and default organisation templates for VINYRD.

Templates provide onboarding defaults only. They do not redefine a church body's
constitution. Organisation levels, office titles and permission suggestions can
be adapted by authorised denomination administrators.
"""

from app.services.localization import localized_label


def position(key, title, permission_role="pastor_leader", *, sw=None):
    labels = {"en": title}
    if sw:
        labels["sw"] = sw
    return {
        "key": key,
        "title": localized_label(labels, "en"),
        "labels": labels,
        "permission_role": permission_role,
    }


def level(key, label, *positions, optional=False, sw=None):
    labels = {"en": label}
    if sw:
        labels["sw"] = sw
    return {
        "key": key,
        "label": localized_label(labels, "en"),
        "labels": labels,
        "optional": optional,
        "positions": list(positions),
    }


DENOMINATION_ALIASES = {
    "Catholic": ["Roman Catholic", "Catholic Church"],
    "Lutheran": ["ELCT", "KKKT", "Evangelical Lutheran Church in Tanzania"],
    "Anglican": ["ACT", "KAT", "Anglican Church of Tanzania"],
    "Moravian": ["KMT", "Moravian Church in Tanzania"],
    "Africa Inland Church": ["AICT", "Africa Inland Church Tanzania"],
    "Assemblies of God": ["TAG", "Tanzania Assemblies of God"],
    "Seventh-day Adventist": ["SDA", "Seventh Day Adventist"],
    "New Apostolic": ["NAC", "New Apostolic Church"],
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
                position("archbishop", "Archbishop", "administrator"),
                position("vicar_general", "Vicar General", "administrator"),
                position("chancellor", "Chancellor", "administrator"),
                position("bursar_treasurer", "Bursar / Treasurer", "accountant"),
                optional=True,
            ),
            level(
                "diocese",
                "Diocese",
                position("bishop", "Bishop", "administrator"),
                position("vicar_general", "Vicar General", "administrator"),
                position("chancellor", "Chancellor", "administrator"),
                position("diocesan_bursar_treasurer", "Diocesan Bursar / Treasurer", "accountant"),
            ),
            level(
                "deanery",
                "Deanery",
                position("dean", "Dean", "pastor_leader"),
                optional=True,
            ),
            level(
                "parish",
                "Parish",
                position("parish_priest", "Parish Priest", "pastor_leader"),
                position("assistant_parish_priest", "Assistant Parish Priest", "pastor_leader"),
                position("parish_secretary", "Parish Secretary", "administrator"),
                position("parish_treasurer", "Parish Treasurer", "accountant"),
            ),
            level(
                "outstation",
                "Outstation / Chaplaincy",
                position(
                    "priest_in_charge_chaplain", "Priest-in-Charge / Chaplain", "pastor_leader"
                ),
                position("catechist", "Catechist", "pastor_leader"),
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
                position(
                    "presiding_bishop_head_of_church",
                    "Presiding Bishop / Head of Church",
                    "administrator",
                ),
                position("secretary_general", "Secretary General", "administrator"),
                position("treasurer_finance_lead", "Treasurer / Finance Lead", "accountant"),
            ),
            level(
                "diocese",
                "Diocese / Mission Area",
                position("diocesan_bishop", "Diocesan Bishop", "administrator"),
                position(
                    "diocesan_general_secretary", "Diocesan General Secretary", "administrator"
                ),
                position("diocesan_treasurer", "Diocesan Treasurer", "accountant"),
            ),
            level(
                "district",
                "District",
                position("district_pastor_dean", "District Pastor / Dean", "pastor_leader"),
                position("district_secretary", "District Secretary", "administrator"),
                optional=True,
            ),
            level(
                "parish",
                "Parish",
                position("parish_pastor", "Parish Pastor", "pastor_leader"),
                position("assistant_pastor", "Assistant Pastor", "pastor_leader"),
                position("parish_secretary", "Parish Secretary", "administrator"),
                position("parish_treasurer", "Parish Treasurer", "accountant"),
            ),
            level(
                "congregation",
                "Congregation",
                position("congregation_pastor", "Congregation Pastor", "pastor_leader"),
                position("congregation_chairperson", "Congregation Chairperson", "administrator"),
                position("congregation_treasurer", "Congregation Treasurer", "accountant"),
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
                position("archbishop", "Archbishop", "administrator"),
                position("dean_of_the_province", "Dean of the Province", "administrator"),
                position("general_secretary", "General Secretary", "administrator"),
                position("provincial_registrar", "Provincial Registrar", "administrator"),
                position("treasurer", "Treasurer", "accountant"),
            ),
            level(
                "diocese",
                "Diocese",
                position("bishop", "Bishop", "administrator"),
                position("diocesan_secretary", "Diocesan Secretary", "administrator"),
                position("diocesan_treasurer", "Diocesan Treasurer", "accountant"),
            ),
            level(
                "archdeaconry",
                "Archdeaconry / Deanery",
                position("archdeacon_dean", "Archdeacon / Dean", "pastor_leader"),
                optional=True,
            ),
            level(
                "parish",
                "Parish",
                position("parish_priest_rector", "Parish Priest / Rector", "pastor_leader"),
                position("assistant_priest_curate", "Assistant Priest / Curate", "pastor_leader"),
                position("parish_secretary", "Parish Secretary", "administrator"),
                position("parish_treasurer", "Parish Treasurer", "accountant"),
            ),
            level(
                "local_church",
                "Local Church / Chapelry",
                position("priest_in_charge", "Priest-in-Charge", "pastor_leader"),
                position("lay_leader", "Lay Leader", "pastor_leader"),
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
                position(
                    "presiding_bishop_askofu_kiongozi",
                    "Presiding Bishop (Askofu Kiongozi)",
                    "administrator",
                ),
                position("deputy_presiding_bishop", "Deputy Presiding Bishop", "administrator"),
                position(
                    "general_secretary_katibu_mkuu",
                    "General Secretary (Katibu Mkuu)",
                    "administrator",
                ),
                position(
                    "general_treasurer_mhazini_mkuu",
                    "General Treasurer (Mhazini Mkuu)",
                    "accountant",
                ),
            ),
            level(
                "province",
                "Province",
                position(
                    "bishop_provincial_chairperson",
                    "Bishop / Provincial Chairperson",
                    "administrator",
                ),
                position("provincial_secretary", "Provincial Secretary", "administrator"),
                position("provincial_treasurer", "Provincial Treasurer", "accountant"),
            ),
            level(
                "district",
                "District",
                position(
                    "district_chairperson_pastor", "District Chairperson / Pastor", "pastor_leader"
                ),
                position("district_secretary", "District Secretary", "administrator"),
            ),
            level(
                "ward",
                "Ward / Parish",
                position("parish_pastor", "Parish Pastor", "pastor_leader"),
                position("parish_chairperson", "Parish Chairperson", "administrator"),
                optional=True,
            ),
            level(
                "congregation",
                "Congregation",
                position("congregation_pastor", "Congregation Pastor", "pastor_leader"),
                position("congregation_chairperson", "Congregation Chairperson", "administrator"),
                position("congregation_treasurer", "Congregation Treasurer", "accountant"),
            ),
            level(
                "sub_congregation",
                "Sub-congregation",
                position("pastor_evangelist", "Pastor / Evangelist", "pastor_leader"),
                position("local_chairperson", "Local Chairperson", "administrator"),
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
                position("archbishop", "Archbishop", "administrator"),
                position("general_secretary", "General Secretary", "administrator"),
                position("national_treasurer", "National Treasurer", "accountant"),
            ),
            level(
                "diocese",
                "Diocese",
                position("bishop", "Bishop", "administrator"),
                position("diocesan_secretary", "Diocesan Secretary", "administrator"),
                position("diocesan_treasurer", "Diocesan Treasurer", "accountant"),
            ),
            level(
                "pastorate",
                "Pastorate",
                position("pastorate_pastor_leader", "Pastorate Pastor / Leader", "pastor_leader"),
                position("pastorate_secretary", "Pastorate Secretary", "administrator"),
            ),
            level(
                "local_congregation",
                "Local Congregation",
                position("local_church_pastor", "Local Church Pastor", "pastor_leader"),
                position("church_secretary", "Church Secretary", "administrator"),
                position("church_treasurer", "Church Treasurer", "accountant"),
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
                position("president_chairperson", "President / Chairperson", "administrator"),
                position("general_secretary", "General Secretary", "administrator"),
                position("treasurer", "Treasurer", "accountant"),
                optional=True,
            ),
            level(
                "association",
                "Regional Association",
                position("moderator_chairperson", "Moderator / Chairperson", "administrator"),
                position("association_secretary", "Association Secretary", "administrator"),
                position("treasurer", "Treasurer", "accountant"),
                optional=True,
            ),
            level(
                "local_church",
                "Local Church",
                position("senior_pastor_pastor", "Senior Pastor / Pastor", "pastor_leader"),
                position("church_secretary", "Church Secretary", "administrator"),
                position("church_treasurer", "Church Treasurer", "accountant"),
                position("deacon_elder", "Deacon / Elder", "pastor_leader"),
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
                position(
                    "bishop_conference_chairperson",
                    "Bishop / Conference Chairperson",
                    "administrator",
                ),
                position("general_secretary", "General Secretary", "administrator"),
                position("treasurer", "Treasurer", "accountant"),
                optional=True,
            ),
            level(
                "region",
                "Diocese / Region",
                position(
                    "bishop_regional_chairperson", "Bishop / Regional Chairperson", "administrator"
                ),
                position("regional_secretary", "Regional Secretary", "administrator"),
                optional=True,
            ),
            level(
                "district",
                "District / Area",
                position(
                    "district_pastor_chairperson", "District Pastor / Chairperson", "pastor_leader"
                ),
                optional=True,
            ),
            level(
                "congregation",
                "Congregation",
                position("pastor", "Pastor", "pastor_leader"),
                position("church_elder", "Church Elder", "pastor_leader"),
                position("secretary", "Secretary", "administrator"),
                position("treasurer", "Treasurer", "accountant"),
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
                position("moderator", "Moderator", "administrator"),
                position("general_secretary_clerk", "General Secretary / Clerk", "administrator"),
                position("treasurer", "Treasurer", "accountant"),
                optional=True,
            ),
            level(
                "synod",
                "Synod",
                position("synod_moderator", "Synod Moderator", "administrator"),
                position("synod_clerk", "Synod Clerk", "administrator"),
                position("treasurer", "Treasurer", "accountant"),
                optional=True,
            ),
            level(
                "presbytery",
                "Presbytery",
                position("presbytery_moderator", "Presbytery Moderator", "administrator"),
                position("presbytery_clerk", "Presbytery Clerk", "administrator"),
                position("treasurer", "Treasurer", "accountant"),
            ),
            level(
                "congregation",
                "Congregation",
                position("minister_pastor", "Minister / Pastor", "pastor_leader"),
                position("session_clerk", "Session Clerk", "administrator"),
                position("elder", "Elder", "pastor_leader"),
                position("treasurer", "Treasurer", "accountant"),
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
                position("national_overseer_bishop", "National Overseer / Bishop", "administrator"),
                position("general_secretary", "General Secretary", "administrator"),
                position("treasurer", "Treasurer", "accountant"),
                optional=True,
            ),
            level(
                "region",
                "Region / District",
                position(
                    "regional_district_overseer", "Regional / District Overseer", "administrator"
                ),
                position("secretary", "Secretary", "administrator"),
                optional=True,
            ),
            level(
                "local_church",
                "Local Church",
                position("senior_pastor_pastor", "Senior Pastor / Pastor", "pastor_leader"),
                position("church_secretary", "Church Secretary", "administrator"),
                position("treasurer", "Treasurer", "accountant"),
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
                position(
                    "national_leader_chairperson", "National Leader / Chairperson", "administrator"
                ),
                position("general_secretary", "General Secretary", "administrator"),
                optional=True,
            ),
            level(
                "region",
                "Region / District",
                position(
                    "regional_coordinator_overseer",
                    "Regional Coordinator / Overseer",
                    "administrator",
                ),
                optional=True,
            ),
            level(
                "local_church",
                "Local Church",
                position("senior_pastor_pastor", "Senior Pastor / Pastor", "pastor_leader"),
                position("elder", "Elder", "pastor_leader"),
                position("church_secretary", "Church Secretary", "administrator"),
                position("treasurer", "Treasurer", "accountant"),
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
                position("national_bishop_overseer", "National Bishop / Overseer", "administrator"),
                position("general_secretary", "General Secretary", "administrator"),
                position("treasurer", "Treasurer", "accountant"),
                optional=True,
            ),
            level(
                "region",
                "Region / District",
                position(
                    "regional_district_overseer", "Regional / District Overseer", "administrator"
                ),
                position("secretary", "Secretary", "administrator"),
                optional=True,
            ),
            level(
                "local_church",
                "Local Church",
                position("senior_pastor_pastor", "Senior Pastor / Pastor", "pastor_leader"),
                position("church_secretary", "Church Secretary", "administrator"),
                position("treasurer", "Treasurer", "accountant"),
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
                position("territorial_commander", "Territorial Commander", "administrator"),
                position("chief_secretary", "Chief Secretary", "administrator"),
                position("finance_secretary", "Finance Secretary", "accountant"),
            ),
            level(
                "division",
                "Division / District",
                position(
                    "divisional_district_commander",
                    "Divisional / District Commander",
                    "administrator",
                ),
                position("divisional_secretary", "Divisional Secretary", "administrator"),
                optional=True,
            ),
            level(
                "corps",
                "Corps",
                position("corps_officer", "Corps Officer", "pastor_leader"),
                position("corps_secretary", "Corps Secretary", "administrator"),
                position("corps_treasurer", "Corps Treasurer", "accountant"),
            ),
            level(
                "outpost",
                "Outpost",
                position("outpost_officer_leader", "Outpost Officer / Leader", "pastor_leader"),
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
                position("presiding_bishop", "Presiding Bishop", "administrator", sw="Askofu Mkuu"),
                position(
                    "deputy_presiding_bishop",
                    "Deputy Presiding Bishop",
                    "administrator",
                    sw="Makamu Askofu Mkuu",
                ),
                position(
                    "general_secretary", "General Secretary", "administrator", sw="Katibu Mkuu"
                ),
                position(
                    "general_treasurer", "General Treasurer", "accountant", sw="Mtunza Hazina Mkuu"
                ),
                sw="Kanisa la Taifa / Baraza Kuu",
            ),
            level(
                "zone",
                "Zone",
                position(
                    "zone_fellowship_chairperson",
                    "Zone Fellowship Chairperson",
                    "administrator",
                    sw="Mwenyekiti wa Ushirika wa Kanda",
                ),
                position(
                    "zone_secretary_treasurer",
                    "Zone Secretary / Treasurer",
                    "accountant",
                    sw="Katibu / Mtunza Hazina wa Kanda",
                ),
                sw="Kanda",
            ),
            level(
                "district",
                "District",
                position(
                    "district_bishop", "District Bishop", "administrator", sw="Askofu wa Jimbo"
                ),
                position(
                    "deputy_district_bishop",
                    "Deputy District Bishop",
                    "administrator",
                    sw="Makamu Askofu wa Jimbo",
                ),
                position(
                    "district_secretary",
                    "District Secretary",
                    "administrator",
                    sw="Katibu wa Jimbo",
                ),
                position(
                    "district_treasurer",
                    "District Treasurer",
                    "accountant",
                    sw="Mtunza Hazina wa Jimbo",
                ),
                sw="Jimbo",
            ),
            level(
                "section",
                "Section",
                position(
                    "section_overseer",
                    "Section Overseer",
                    "pastor_leader",
                    sw="Mwangalizi wa Sehemu",
                ),
                position(
                    "deputy_section_overseer",
                    "Deputy Section Overseer",
                    "pastor_leader",
                    sw="Makamu Mwangalizi wa Sehemu",
                ),
                position(
                    "section_secretary", "Section Secretary", "administrator", sw="Katibu wa Sehemu"
                ),
                position(
                    "section_treasurer",
                    "Section Treasurer",
                    "accountant",
                    sw="Mtunza Hazina wa Sehemu",
                ),
                sw="Sehemu",
            ),
            level(
                "local_church",
                "Local Church",
                position(
                    "lead_pastor", "Lead / Senior Pastor", "pastor_leader", sw="Mchungaji Kiongozi"
                ),
                position("pastor", "Pastor", "pastor_leader", sw="Mchungaji"),
                position(
                    "church_secretary", "Church Secretary", "administrator", sw="Katibu wa Kanisa"
                ),
                position("church_treasurer", "Treasurer", "accountant", sw="Mtunza Hazina"),
                sw="Kanisa la Mahali Pamoja",
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
                position("president", "President", "administrator"),
                position("executive_secretary", "Executive Secretary", "administrator"),
                position("treasurer", "Treasurer", "accountant"),
            ),
            level(
                "conference",
                "Conference / Field",
                position("president", "President", "administrator"),
                position("executive_secretary", "Executive Secretary", "administrator"),
                position("treasurer", "Treasurer", "accountant"),
            ),
            level(
                "district",
                "District",
                position("district_pastor", "District Pastor", "pastor_leader"),
                optional=True,
            ),
            level(
                "local_church",
                "Local Church / Company",
                position("church_pastor", "Church Pastor", "pastor_leader"),
                position("first_elder_elder", "First Elder / Elder", "pastor_leader"),
                position("church_clerk", "Church Clerk", "administrator"),
                position("church_treasurer", "Church Treasurer", "accountant"),
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
                position("district_apostle", "District Apostle", "administrator"),
                position("district_apostle_helper", "District Apostle Helper", "administrator"),
            ),
            level(
                "apostle_area",
                "Apostle Area",
                position("apostle", "Apostle", "administrator"),
                position("bishop", "Bishop", "administrator"),
                optional=True,
            ),
            level(
                "district",
                "District",
                position(
                    "district_rector_district_elder",
                    "District Rector / District Elder",
                    "pastor_leader",
                ),
                position("district_evangelist", "District Evangelist", "pastor_leader"),
            ),
            level(
                "congregation",
                "Congregation",
                position("rector", "Rector", "pastor_leader"),
                position("priest", "Priest", "pastor_leader"),
                position("deacon", "Deacon", "pastor_leader"),
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
                position(
                    "presiding_bishop_general_overseer",
                    "Presiding Bishop / General Overseer",
                    "administrator",
                ),
                position("general_secretary", "General Secretary", "administrator"),
                position("treasurer", "Treasurer", "accountant"),
                optional=True,
            ),
            level(
                "region",
                "Region / Zone",
                position("regional_bishop_overseer", "Regional Bishop / Overseer", "administrator"),
                position("regional_secretary", "Regional Secretary", "administrator"),
                optional=True,
            ),
            level(
                "district",
                "District / Section",
                position(
                    "district_section_overseer", "District / Section Overseer", "pastor_leader"
                ),
                position("secretary", "Secretary", "administrator"),
                optional=True,
            ),
            level(
                "local_church",
                "Local Church",
                position(
                    "senior_pastor_lead_pastor", "Senior Pastor / Lead Pastor", "pastor_leader"
                ),
                position("associate_pastor", "Associate Pastor", "pastor_leader"),
                position(
                    "church_administrator_secretary",
                    "Church Administrator / Secretary",
                    "administrator",
                ),
                position("treasurer", "Treasurer", "accountant"),
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
                position("patriarch_primate", "Patriarch / Primate", "administrator"),
                position("general_secretary", "General Secretary", "administrator"),
                optional=True,
            ),
            level(
                "archdiocese",
                "Archdiocese / Metropolis",
                position("archbishop_metropolitan", "Archbishop / Metropolitan", "administrator"),
                position("diocesan_secretary", "Diocesan Secretary", "administrator"),
                position("treasurer", "Treasurer", "accountant"),
            ),
            level(
                "parish",
                "Parish / Mission",
                position(
                    "parish_priest_priest_in_charge",
                    "Parish Priest / Priest-in-Charge",
                    "pastor_leader",
                ),
                position("deacon", "Deacon", "pastor_leader"),
                position("parish_secretary", "Parish Secretary", "administrator"),
                position("treasurer", "Treasurer", "accountant"),
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
                position(
                    "presiding_bishop_conference_president",
                    "Presiding Bishop / Conference President",
                    "administrator",
                ),
                position("conference_secretary", "Conference Secretary", "administrator"),
                position("treasurer", "Treasurer", "accountant"),
                optional=True,
            ),
            level(
                "district",
                "District / Circuit",
                position(
                    "district_superintendent_circuit_superintendent",
                    "District Superintendent / Circuit Superintendent",
                    "administrator",
                ),
                position("circuit_minister", "Circuit Minister", "pastor_leader"),
            ),
            level(
                "local_church",
                "Local Church / Society",
                position("minister_pastor", "Minister / Pastor", "pastor_leader"),
                position("lay_leader", "Lay Leader", "pastor_leader"),
                position("church_secretary", "Church Secretary", "administrator"),
                position("treasurer", "Treasurer", "accountant"),
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
                position("founder_presiding_leader", "Founder / Presiding Leader", "administrator"),
                position(
                    "executive_director_administrator",
                    "Executive Director / Administrator",
                    "administrator",
                ),
                position("finance_lead_treasurer", "Finance Lead / Treasurer", "accountant"),
                optional=True,
            ),
            level(
                "campus",
                "Campus / Branch",
                position(
                    "campus_pastor_branch_pastor", "Campus Pastor / Branch Pastor", "pastor_leader"
                ),
                position("campus_administrator", "Campus Administrator", "administrator"),
                position("finance_lead", "Finance Lead", "accountant"),
                optional=True,
            ),
            level(
                "local_church",
                "Local Church",
                position(
                    "lead_pastor_senior_pastor", "Lead Pastor / Senior Pastor", "pastor_leader"
                ),
                position("associate_pastor", "Associate Pastor", "pastor_leader"),
                position(
                    "church_administrator_secretary",
                    "Church Administrator / Secretary",
                    "administrator",
                ),
                position("treasurer", "Treasurer", "accountant"),
            ),
        ],
    },
]


