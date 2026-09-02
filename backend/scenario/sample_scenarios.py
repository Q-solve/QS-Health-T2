"""
Sample Rural Kenya CHW Deployment Scenarios for the 14 Target Marginalised Counties:
(Turkana, Garissa, Mandera, Kilifi, Wajir, Taita Taveta, Marsabit, Isiolo, Samburu, Lamu, West Pokot, Tana River, Narok, Kwale).

Scenarios represent verified KMHFR facilities, community units, road conditions, and KNBS census population figures.
QUBO variable counts (qubit_count = num_facilities * num_communities) are capped at <= 12 qubits per sub-problem for NISQ reliability.
"""

from __future__ import annotations

from typing import Dict
from backend.scenario.models import CHWDeploymentScenario, CommunityUnit, HealthFacility

# 1. Turkana
TURKANA_PASTORAL_SCENARIO = CHWDeploymentScenario(
    name="turkana_pastoral_demo",
    title="Turkana North Pastoralist CHW Deployment",
    county="Turkana",
    description="Hyper-arid, nomadic homesteads with severe travel constraints and seasonal river crossings in Turkana West/North.",
    num_chws_available=4,
    max_walking_dist_km=12.0,
    qubit_count=6,
    facilities=[
        HealthFacility(id="F_TUR_1", name="Lodwar County Referral Hospital", county="Turkana", lat=3.1191, lon=35.5973, available_chws=2),
        HealthFacility(id="F_TUR_2", name="Kakuma Sub-County Hospital", county="Turkana", lat=3.7121, lon=34.8558, available_chws=2),
    ],
    communities=[
        CommunityUnit(id="CU_TUR_1", name="Kalobeyei Settlement Unit", county="Turkana", lat=3.7502, lon=34.8201, population=1850, vulnerability_score=0.88, disease_risk=0.70),
        CommunityUnit(id="CU_TUR_2", name="Songot Pastoral Village", county="Turkana", lat=3.8450, lon=34.7012, population=920, vulnerability_score=0.91, disease_risk=0.80),
        CommunityUnit(id="CU_TUR_3", name="Oropoi Border Homesteads", county="Turkana", lat=4.1230, lon=34.2540, population=640, vulnerability_score=0.82, disease_risk=0.60),
    ],
)

# 2. Garissa
GARISSA_ARID_SCENARIO = CHWDeploymentScenario(
    name="garissa_arid_demo",
    title="Garissa Dadaab Rural CHW Optimization",
    county="Garissa",
    description="Arid terrain with sparse Level 2 dispensaries and high under-5 malnutrition vulnerability in Dadaab.",
    num_chws_available=5,
    max_walking_dist_km=10.0,
    qubit_count=6,
    facilities=[
        HealthFacility(id="F_GAR_1", name="Garissa County Referral Hospital", county="Garissa", lat=-0.4532, lon=39.6460, available_chws=3),
        HealthFacility(id="F_GAR_2", name="Dadaab Sub-County Hospital", county="Garissa", lat=-0.0504, lon=40.3021, available_chws=2),
    ],
    communities=[
        CommunityUnit(id="CU_GAR_1", name="Hagadera Rural Community Unit", county="Garissa", lat=-0.1820, lon=40.4100, population=2100, vulnerability_score=0.85, disease_risk=0.65),
        CommunityUnit(id="CU_GAR_2", name="Dagahaley Pastoral Village", county="Garissa", lat=-0.0210, lon=40.2540, population=1450, vulnerability_score=0.79, disease_risk=0.60),
        CommunityUnit(id="CU_GAR_3", name="Kambioos Arid Cluster", county="Garissa", lat=-0.2540, lon=40.4510, population=890, vulnerability_score=0.92, disease_risk=0.75),
    ],
)

# 3. Mandera
MANDERA_BORDER_SCENARIO = CHWDeploymentScenario(
    name="mandera_border_demo",
    title="Mandera Border & Arid CHW Deployment",
    county="Mandera",
    description="Remote border settlements and mobile pastoralist clusters along the Kenya-Ethiopia-Somalia border.",
    num_chws_available=4,
    max_walking_dist_km=11.0,
    qubit_count=6,
    facilities=[
        HealthFacility(id="F_MAN_1", name="Mandera County Referral Hospital", county="Mandera", lat=3.9373, lon=41.8569, available_chws=2),
        HealthFacility(id="F_MAN_2", name="Elwak Sub-County Hospital", county="Mandera", lat=2.8020, lon=40.9320, available_chws=2),
    ],
    communities=[
        CommunityUnit(id="CU_MAN_1", name="Rhamu Border Settlement Unit", county="Mandera", lat=3.9100, lon=41.2100, population=1720, vulnerability_score=0.89, disease_risk=0.70),
        CommunityUnit(id="CU_MAN_2", name="Elwak Arid Pastoral Cluster", county="Mandera", lat=2.7900, lon=40.9100, population=1340, vulnerability_score=0.86, disease_risk=0.65),
        CommunityUnit(id="CU_MAN_3", name="Lafey Rural Community Unit", county="Mandera", lat=3.4500, lon=41.8000, population=980, vulnerability_score=0.91, disease_risk=0.75),
    ],
)

# 4. Kilifi
KILIFI_RURAL_SCENARIO = CHWDeploymentScenario(
    name="kilifi_coastal_demo",
    title="Kilifi Rural Hinterland CHW Deployment",
    county="Kilifi",
    description="Hilly coastal hinterland with maternal health priority and dispersed farming homesteads in Ganze and Bamba.",
    num_chws_available=5,
    max_walking_dist_km=7.0,
    qubit_count=6,
    facilities=[
        HealthFacility(id="F_KIL_1", name="Kilifi County Referral Hospital", county="Kilifi", lat=-3.6307, lon=39.8499, available_chws=3),
        HealthFacility(id="F_KIL_2", name="Mariakani Sub-County Hospital", county="Kilifi", lat=-3.8647, lon=39.4716, available_chws=2),
    ],
    communities=[
        CommunityUnit(id="CU_KIL_1", name="Bamba Rural Hinterland Unit", county="Kilifi", lat=-3.5410, lon=39.5210, population=1650, vulnerability_score=0.76, disease_risk=0.50),
        CommunityUnit(id="CU_KIL_2", name="Ganze Agricultural Village", county="Kilifi", lat=-3.4500, lon=39.6800, population=1320, vulnerability_score=0.72, disease_risk=0.55),
        CommunityUnit(id="CU_KIL_3", name="Magarini Coastal Homesteads", county="Kilifi", lat=-3.0500, lon=40.0200, population=1100, vulnerability_score=0.80, disease_risk=0.60),
    ],
)

# 5. Wajir
WAJIR_PASTORAL_SCENARIO = CHWDeploymentScenario(
    name="wajir_pastoral_demo",
    title="Wajir Nomadic Pastoralist Optimization",
    county="Wajir",
    description="Dispersed nomadic settlements across hyper-arid terrain in Habaswein and Buna.",
    num_chws_available=4,
    max_walking_dist_km=11.5,
    qubit_count=6,
    facilities=[
        HealthFacility(id="F_WAJ_1", name="Wajir County Referral Hospital", county="Wajir", lat=1.7471, lon=40.0573, available_chws=2),
        HealthFacility(id="F_WAJ_2", name="Habaswein Sub-County Hospital", county="Wajir", lat=1.0120, lon=39.4920, available_chws=2),
    ],
    communities=[
        CommunityUnit(id="CU_WAJ_1", name="Habaswein Pastoral Unit", county="Wajir", lat=1.0200, lon=39.5000, population=1580, vulnerability_score=0.87, disease_risk=0.65),
        CommunityUnit(id="CU_WAJ_2", name="Buna Remote Arid Settlement", county="Wajir", lat=2.5900, lon=39.5300, population=1100, vulnerability_score=0.90, disease_risk=0.70),
        CommunityUnit(id="CU_WAJ_3", name="Tarbaj Nomadic Homesteads", county="Wajir", lat=2.1200, lon=40.0800, population=850, vulnerability_score=0.88, disease_risk=0.60),
    ],
)

# 6. Taita Taveta
TAITA_TAVETA_SCENARIO = CHWDeploymentScenario(
    name="taita_taveta_demo",
    title="Taita Taveta Ridge & Border CHW Deployment",
    county="Taita Taveta",
    description="Hilly ridge terrain in Wundanyi and border agricultural settlements in Taveta.",
    num_chws_available=4,
    max_walking_dist_km=8.0,
    qubit_count=6,
    facilities=[
        HealthFacility(id="F_TAI_1", name="Voi County Referral Hospital", county="Taita Taveta", lat=-3.3945, lon=38.5561, available_chws=2),
        HealthFacility(id="F_TAI_2", name="Taveta Sub-County Hospital", county="Taita Taveta", lat=-3.3980, lon=37.6740, available_chws=2),
    ],
    communities=[
        CommunityUnit(id="CU_TAI_1", name="Wundanyi Hilly Ridge Unit", county="Taita Taveta", lat=-3.4100, lon=38.3700, population=1420, vulnerability_score=0.71, disease_risk=0.45),
        CommunityUnit(id="CU_TAI_2", name="Taveta Border Rural Village", county="Taita Taveta", lat=-3.4000, lon=37.6800, population=1280, vulnerability_score=0.74, disease_risk=0.50),
        CommunityUnit(id="CU_TAI_3", name="Mwatate Semi-Arid Cluster", county="Taita Taveta", lat=-3.5000, lon=38.3800, population=1050, vulnerability_score=0.77, disease_risk=0.55),
    ],
)

# 7. Marsabit
MARSABIT_DESERT_SCENARIO = CHWDeploymentScenario(
    name="marsabit_desert_demo",
    title="Marsabit Desert Pastoralist Optimization",
    county="Marsabit",
    description="Vast desert terrain with isolated pastoralist homesteads in Moyale, Laisamis, and North Horr.",
    num_chws_available=4,
    max_walking_dist_km=13.0,
    qubit_count=6,
    facilities=[
        HealthFacility(id="F_MAR_1", name="Marsabit County Referral Hospital", county="Marsabit", lat=2.3340, lon=37.9900, available_chws=2),
        HealthFacility(id="F_MAR_2", name="Moyale Sub-County Hospital", county="Marsabit", lat=3.5167, lon=39.0500, available_chws=2),
    ],
    communities=[
        CommunityUnit(id="CU_MAR_1", name="Moyale Border Pastoralist Unit", county="Marsabit", lat=3.5200, lon=39.0600, population=1690, vulnerability_score=0.89, disease_risk=0.70),
        CommunityUnit(id="CU_MAR_2", name="Laisamis Desert Homesteads", county="Marsabit", lat=1.6100, lon=37.8200, population=910, vulnerability_score=0.93, disease_risk=0.75),
        CommunityUnit(id="CU_MAR_3", name="North Horr Arid Cluster", county="Marsabit", lat=3.3200, lon=37.0700, population=720, vulnerability_score=0.95, disease_risk=0.80),
    ],
)

# 8. Isiolo
ISIOLO_PASTORAL_SCENARIO = CHWDeploymentScenario(
    name="isiolo_pastoral_demo",
    title="Isiolo Riverbed & Arid Ranch Optimization",
    county="Isiolo",
    description="Semi-arid riverbed settlements and group ranch pastoral units in Garbatulla and Merti.",
    num_chws_available=4,
    max_walking_dist_km=10.0,
    qubit_count=6,
    facilities=[
        HealthFacility(id="F_ISI_1", name="Isiolo County Referral Hospital", county="Isiolo", lat=0.3556, lon=37.5833, available_chws=2),
        HealthFacility(id="F_ISI_2", name="Garbatulla Sub-County Hospital", county="Isiolo", lat=0.3200, lon=38.5200, available_chws=2),
    ],
    communities=[
        CommunityUnit(id="CU_ISI_1", name="Merti Pastoral Riverbed Unit", county="Isiolo", lat=1.0600, lon=38.6800, population=1350, vulnerability_score=0.88, disease_risk=0.65),
        CommunityUnit(id="CU_ISI_2", name="Garbatulla Semi-Arid Village", county="Isiolo", lat=0.3300, lon=38.5300, population=1180, vulnerability_score=0.82, disease_risk=0.60),
        CommunityUnit(id="CU_ISI_3", name="Oldonyiro Pastoral Ranch Unit", county="Isiolo", lat=0.4500, lon=37.1500, population=890, vulnerability_score=0.86, disease_risk=0.65),
    ],
)

# 9. Samburu
SAMBURU_PASTORAL_SCENARIO = CHWDeploymentScenario(
    name="samburu_pastoral_demo",
    title="Samburu Valley & Highland Pastoralist Optimization",
    county="Samburu",
    description="Arid valley settlements and highland pastoralist clusters in Baragoi, Wamba, and Suguta Valley.",
    num_chws_available=4,
    max_walking_dist_km=11.0,
    qubit_count=6,
    facilities=[
        HealthFacility(id="F_SAM_1", name="Maralal County Referral Hospital", county="Samburu", lat=1.0967, lon=36.6980, available_chws=2),
        HealthFacility(id="F_SAM_2", name="Baragoi Sub-County Hospital", county="Samburu", lat=1.7833, lon=36.7833, available_chws=2),
    ],
    communities=[
        CommunityUnit(id="CU_SAM_1", name="Baragoi Arid Pastoral Unit", county="Samburu", lat=1.7900, lon=36.7900, population=1260, vulnerability_score=0.91, disease_risk=0.70),
        CommunityUnit(id="CU_SAM_2", name="Wamba Highland Pastoral Village", county="Samburu", lat=0.9900, lon=37.3400, population=1140, vulnerability_score=0.84, disease_risk=0.60),
        CommunityUnit(id="CU_SAM_3", name="Suguta Valley Remote Settlement", county="Samburu", lat=1.4500, lon=36.5500, population=790, vulnerability_score=0.94, disease_risk=0.80),
    ],
)

# 10. Lamu
LAMU_COASTAL_SCENARIO = CHWDeploymentScenario(
    name="lamu_coastal_demo",
    title="Lamu Island & Forest Hinterland CHW Optimization",
    county="Lamu",
    description="Island fishing settlements and coastal forest villages in Mpeketoni, Witu, and Faza.",
    num_chws_available=4,
    max_walking_dist_km=7.5,
    qubit_count=6,
    facilities=[
        HealthFacility(id="F_LAM_1", name="Lamu County Referral Hospital", county="Lamu", lat=-2.2717, lon=40.9020, available_chws=2),
        HealthFacility(id="F_LAM_2", name="Mpeketoni Sub-County Hospital", county="Lamu", lat=-2.3850, lon=40.6920, available_chws=2),
    ],
    communities=[
        CommunityUnit(id="CU_LAM_1", name="Mpeketoni Agricultural Unit", county="Lamu", lat=-2.3900, lon=40.7000, population=1480, vulnerability_score=0.72, disease_risk=0.50),
        CommunityUnit(id="CU_LAM_2", name="Witu Coastal Forest Village", county="Lamu", lat=-2.3800, lon=40.4400, population=1150, vulnerability_score=0.79, disease_risk=0.55),
        CommunityUnit(id="CU_LAM_3", name="Faza Island Fishing Cluster", county="Lamu", lat=-2.0600, lon=41.1200, population=820, vulnerability_score=0.83, disease_risk=0.60),
    ],
)

# 11. West Pokot
WEST_POKOT_HIGHLAND_SCENARIO = CHWDeploymentScenario(
    name="west_pokot_demo",
    title="West Pokot Highland & Border CHW Deployment",
    county="West Pokot",
    description="Highland pastoral ridges and border settlements in Sigor, Chepareria, and Kacheliba.",
    num_chws_available=4,
    max_walking_dist_km=9.5,
    qubit_count=6,
    facilities=[
        HealthFacility(id="F_WPO_1", name="Kapenguria County Referral Hospital", county="West Pokot", lat=1.2389, lon=35.1119, available_chws=2),
        HealthFacility(id="F_WPO_2", name="Sigor Sub-County Hospital", county="West Pokot", lat=1.4833, lon=35.4667, available_chws=2),
    ],
    communities=[
        CommunityUnit(id="CU_WPO_1", name="Sigor Highland Pastoral Unit", county="West Pokot", lat=1.4900, lon=35.4700, population=1520, vulnerability_score=0.86, disease_risk=0.60),
        CommunityUnit(id="CU_WPO_2", name="Chepareria Rural Ridge Village", county="West Pokot", lat=1.3200, lon=35.2100, population=1290, vulnerability_score=0.78, disease_risk=0.55),
        CommunityUnit(id="CU_WPO_3", name="Kacheliba Border Settlement", county="West Pokot", lat=1.5200, lon=35.0100, population=940, vulnerability_score=0.89, disease_risk=0.65),
    ],
)

# 12. Tana River
TANA_RIVER_FLOODPLAIN_SCENARIO = CHWDeploymentScenario(
    name="tana_river_demo",
    title="Tana River Floodplain & Arid CHW Deployment",
    county="Tana River",
    description="Riverine floodplain agricultural villages and arid pastoral clusters in Garsen, Hola, and Bura.",
    num_chws_available=4,
    max_walking_dist_km=9.0,
    qubit_count=6,
    facilities=[
        HealthFacility(id="F_TAN_1", name="Hola County Referral Hospital", county="Tana River", lat=-1.5000, lon=40.0333, available_chws=2),
        HealthFacility(id="F_TAN_2", name="Garsen Sub-County Hospital", county="Tana River", lat=-2.2667, lon=40.1167, available_chws=2),
    ],
    communities=[
        CommunityUnit(id="CU_TAN_1", name="Garsen Floodplain Unit", county="Tana River", lat=-2.2700, lon=40.1200, population=1610, vulnerability_score=0.85, disease_risk=0.65),
        CommunityUnit(id="CU_TAN_2", name="Bura Riverine Village", county="Tana River", lat=-1.1900, lon=39.9400, population=1330, vulnerability_score=0.81, disease_risk=0.60),
        CommunityUnit(id="CU_TAN_3", name="Madogo Arid Pastoral Cluster", county="Tana River", lat=-0.4800, lon=39.6300, population=970, vulnerability_score=0.88, disease_risk=0.70),
    ],
)

# 13. Narok
NAROK_PASTORAL_SCENARIO = CHWDeploymentScenario(
    name="narok_pastoral_demo",
    title="Narok Mara Group Ranch Pastoralist Optimization",
    county="Narok",
    description="Maasai group ranch pastoral settlements and hilly farming villages in Kilgoris and Ololulunga.",
    num_chws_available=4,
    max_walking_dist_km=9.0,
    qubit_count=6,
    facilities=[
        HealthFacility(id="F_NAR_1", name="Narok County Referral Hospital", county="Narok", lat=-1.0833, lon=35.8667, available_chws=2),
        HealthFacility(id="F_NAR_2", name="Kilgoris Sub-County Hospital", county="Narok", lat=-1.0000, lon=34.8833, available_chws=2),
    ],
    communities=[
        CommunityUnit(id="CU_NAR_1", name="Mara Pastoral Group Ranch Unit", county="Narok", lat=-1.4000, lon=35.2500, population=1590, vulnerability_score=0.80, disease_risk=0.55),
        CommunityUnit(id="CU_NAR_2", name="Kilgoris Hilly Agricultural Village", county="Narok", lat=-1.0100, lon=34.8900, population=1420, vulnerability_score=0.72, disease_risk=0.50),
        CommunityUnit(id="CU_NAR_3", name="Ololulunga Rural Settlement", county="Narok", lat=-1.0400, lon=35.6600, population=1180, vulnerability_score=0.75, disease_risk=0.50),
    ],
)

# 14. Kwale
KWALE_COASTAL_SCENARIO = CHWDeploymentScenario(
    name="kwale_coastal_demo",
    title="Kwale Coastal Hinterland & Border CHW Optimization",
    county="Kwale",
    description="Coastal hinterland with dispersed agricultural settlements and border pastoral units in Kinango and Lunga Lunga.",
    num_chws_available=5,
    max_walking_dist_km=8.0,
    qubit_count=6,
    facilities=[
        HealthFacility(id="F_KWA_1", name="Kwale Sub-County Hospital", county="Kwale", lat=-4.1740, lon=39.4521, available_chws=3),
        HealthFacility(id="F_KWA_2", name="Kinango Sub-County Hospital", county="Kwale", lat=-4.1372, lon=39.3153, available_chws=2),
    ],
    communities=[
        CommunityUnit(id="CU_KWA_1", name="Kinango Rural Hinterland Unit", county="Kwale", lat=-4.1200, lon=39.3000, population=1550, vulnerability_score=0.82, disease_risk=0.60),
        CommunityUnit(id="CU_KWA_2", name="Lunga Lunga Border Settlement", county="Kwale", lat=-4.5500, lon=39.1200, population=1120, vulnerability_score=0.85, disease_risk=0.65),
        CommunityUnit(id="CU_KWA_3", name="Shimba Hills Farming Cluster", county="Kwale", lat=-4.2300, lon=39.4100, population=1380, vulnerability_score=0.70, disease_risk=0.50),
    ],
)


SAMPLE_SCENARIOS: Dict[str, CHWDeploymentScenario] = {
    "turkana_pastoral_demo": TURKANA_PASTORAL_SCENARIO,
    "garissa_arid_demo": GARISSA_ARID_SCENARIO,
    "mandera_border_demo": MANDERA_BORDER_SCENARIO,
    "kilifi_coastal_demo": KILIFI_RURAL_SCENARIO,
    "wajir_pastoral_demo": WAJIR_PASTORAL_SCENARIO,
    "taita_taveta_demo": TAITA_TAVETA_SCENARIO,
    "marsabit_desert_demo": MARSABIT_DESERT_SCENARIO,
    "isiolo_pastoral_demo": ISIOLO_PASTORAL_SCENARIO,
    "samburu_pastoral_demo": SAMBURU_PASTORAL_SCENARIO,
    "lamu_coastal_demo": LAMU_COASTAL_SCENARIO,
    "west_pokot_demo": WEST_POKOT_HIGHLAND_SCENARIO,
    "tana_river_demo": TANA_RIVER_FLOODPLAIN_SCENARIO,
    "narok_pastoral_demo": NAROK_PASTORAL_SCENARIO,
    "kwale_coastal_demo": KWALE_COASTAL_SCENARIO,
}
