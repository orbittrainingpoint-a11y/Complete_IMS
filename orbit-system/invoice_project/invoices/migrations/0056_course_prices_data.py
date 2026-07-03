from decimal import Decimal
from django.db import migrations


# CSV columns: code, name, oo_intermediate, oo_professional, oo_advanced,
#              priv_intermediate, priv_professional, priv_advanced
PRICES = [
    ('CC',  'CCTV Course',                              1200,    1500,    1800,    2400,    3000,    3600),
    ('IP',  'Premier Pro',                               960,    1200,    1440,    1920,    2400,    2880),
    ('DS',  'After Effects Course',                      960,    1200,    1440,    1920,    2400,    2880),
    ('DA',  'Data Analytics Course',                    2250,    3000,    3600,    4500,    6000,    7200),
    ('PP',  'CapCut Course',                             960,    1200,    1440,    1920,    2400,    2880),
    ('SM',  'SMO Course',                                960,    1200,    1440,    1920,    2400,    2880),
    ('SE',  'SEO Course',                                960,    1200,    1440,    1920,    2400,    2880),
    ('DM',  'Digital Marketing 360 Course',             3150,    4200,    5040,    6300,    8400,   10080),
    ('DC',  'Digital Marketing Course',                 2250,    3000,    3600,    4500,    6000,    7200),
    ('ME',  'Microsoft Excel Advanced',                  960,    1200,    1440,    1920,    2400,    2880),
    ('EX',  'Microsoft Excel Course',                    720,     900,    1080,    1440,    1800,    2160),
    ('MO',  'Microsoft Office Advance Course',          1530,    2040,    2448,    3060,    4080,    4896),
    ('MB',  'Microsoft Office Course',                  1056,    1320,    1584,    2112,    2640,    3168),
    ('PY',  'Python Course',                            1152,    1440,    1728,    2304,    2880,    3456),
    ('BD',  'Back End (Python) Development Course',     1152,    1440,    1728,    2304,    2880,    3456),
    ('FD',  'Front End (React) Development Course',     1152,    1440,    1728,    2304,    2880,    3456),
    ('BP',  'Back End (php) Development Course',        1152,    1440,    1728,    2304,    2880,    3456),
    ('FH',  'Front End (HTML) Development Course',      1152,    1440,    1728,    2304,    2880,    3456),
    ('PD',  'php Development Course',                   1152,    1440,    1728,    2304,    2880,    3456),
    ('CN',  'CCNP Course',                              1260,    1680,    2016,    2520,    3360,    4032),
    ('CA',  'CCNA Course',                              1170,    1560,    1872,    2340,    3120,    3744),
    ('RO',  'Robotics Course',                          1800,    2400,    2880,    3600,    4800,    5760),
    ('DI',  'Dialux Course',                            1200,    1500,    1800,    2400,    3000,    3600),
    ('ST',  'Solar Technician Course',                  1200,    1500,    1800,    2400,    3000,    3600),
    ('SS',  'Solar Simulation Course',                  1260,    1680,    2016,    2520,    3360,    4032),
    ('SPS', 'Solar Pro Simulation Course',              1575,    2100,    2520,    3150,    4200,    5040),
    ('SC',  'Solar Professional Course',                1350,    1800,    2160,    2700,    3600,    4320),
    ('CV',  'Canva Course',                              720,     900,    1080,    1440,    1800,    2160),
    ('VE',  'Video Editing (PP+AE) Course',             1575,    2100,    2520,    3150,    4200,    5040),
    ('GD',  'Graphic Design (AI+PS+XD/Figma) Course',  1440,    1920,    2304,    2880,    3840,    4608),
    ('GA',  'Graphic Design (AI+PS+ID) Course',         1440,    1920,    2304,    2880,    3840,    4608),
    ('GP',  'Graphic Design (AI+PS) Course',            1170,    1560,    1872,    2340,    3120,    3744),
    ('MP',  'Microsoft Project Course',                 1170,    1560,    1872,    2340,    3120,    3744),
    ('P6',  'Primavera P6 Course',                      1305,    1740,    2088,    2610,    3480,    4176),
    ('TS',  'Tekla Structure Course',                   1260,    1680,    2016,    2520,    3360,    4032),
    ('STP', 'STAAD Pro Course',                         1350,    1800,    2160,    2700,    3600,    4320),
    ('FU',  'Fusion 360 Course',                        1260,    1680,    2016,    2520,    3360,    4032),
    ('IN',  'AutoDesk Inventor',                        1440,    1920,    2304,    2880,    3840,    4608),
    ('SW',  'Solidworks Course',              '1512.00','2016.00','2419.20','3024.00','4032.00','4838.40'),
    ('LU',  'Lumion Course',                            1200,    1500,    1800,    2400,    3000,    3600),
    ('VR',  'Vray Course',                              1200,    1500,    1800,    2400,    3000,    3600),
    ('3D',  '3DS Max Course',                           1350,    1800,    2160,    2700,    3600,    4320),
    ('RH',  'Rhino Course',                             1440,    1920,    2304,    2880,    3840,    4608),
    ('NW',  'Navisworks Course',                        1152,    1440,    1728,    2304,    2880,    3456),
    ('RBT', 'Revit BIM Technician Course',              3000,    3000,    3600,    6000,    6000,    7200),
    ('RBC', 'Revit BIM Co-Ordinator Course',            4500,    4500,    5400,    9000,    9000,   10800),
    ('RI',  'Revit Infrastructure Course',              2040,    2040,    2448,    4080,    4080,    4896),
    ('RM',  'Revit MEP Course',                         1170,    1560,    1872,    2340,    3120,    3744),
    ('AC',  'AutoCAD Civil 3D Course',                  2025,    2700,    3240,    4050,    5400,    6480),
    ('ACE', 'AutoCAD Electrical Course',                1200,    1500,    1800,    2400,    3000,    3600),
    ('RS',  'Revit Structure Course',                   1170,    1560,    1872,    2340,    3120,    3744),
    ('RA',  'Revit Architecture Course',                1170,    1560,    1872,    2340,    3120,    3744),
    ('AU',  'AutoCAD 2D & 3D Course',                   1008,    1260,    1512,    2016,    2520,    3024),
    ('FS',  'Full Stack Web Development',               1800,    2400,    2880,    3600,    4800,    5760),
    ('CP',  'C++',                                      1200,    1500,    1800,    2400,    3000,    3600),
    ('WF',  'Wordpress Development',                    1056,    1320,    1584,    2112,    2640,    3168),
    ('ID',  'Interior Design ( 6 Months )',             4050,    5400,    6480,    8100,   10800,   12960),
    ('SU',  'Sketch Up',                                1152,    1440,    1728,    2304,    2880,    3456),
    ('AM',  'AUTOCAD 2D MEP',                           1056,    1320,    1584,    2112,    2640,    3168),
    ('REE', 'React.js Course External',                 1200,    1500,    1800,    2400,    3000,    3600),
    ('B36', 'BIM 360',                                  1200,    1500,    1800,    2400,    3000,    3600),
    ('DIL', 'DIALux Course',                             720,     900,    1080,    1440,    1800,    2160),
    ('CRE', 'Creo Parametric',                          1800,    2400,    2880,    3600,    4800,    5760),
    ('COR', 'Corona',                                   1800,    2400,    2880,    3600,    4800,    5760),
    ('ID1', 'Interior Design ( 1 year)',                9000,   12000,   14400,   18000,   24000,   28800),
    ('M36', 'Microsoft 365 Course',                     1305,    1740,    2088,    2610,    3480,    4176),
    ('OUT', 'Outlook Course',                            816,    1020,    1224,    1632,    2040,    2448),
    ('ID3', 'Interior Design (3 Months)',               2700,    3600,    4320,    5400,    7200,    8640),
    ('PS',  'Photoshop',                                 864,    1080,    1296,    1728,    2160,    2592),
    ('AID', 'Adobe InDesign',                            720,     900,    1080,    1440,    1800,    2160),
    ('MRN', 'Mern Web Development',                     2250,    3000,    3600,    4500,    6000,    7200),
    ('ECM', 'E-commerce Development & Marketing',       1800,    2400,    2880,    3600,    4800,    5760),
    ('PVS', 'Solar PV Syst',                            1152,    1440,    1728,    2304,    2880,    3456),
    ('ILL', 'Illustrator',                               768,     960,    1152,    1536,    1920,    2304),
    ('FEX', 'Financial Excel Course',                   1056,    1320,    1584,    2112,    2640,    3168),
    ('RHM', 'Rhino-matrix Course (Jwellery Design)',    2520,    3360,    4032,    5040,    6720,    8064),
    ('MEC', 'Figma',                                    1056,    1320,    1584,    2112,    2640,    3168),
    ('PLN', 'Planswift',                                1200,    1500,    1800,    2400,    3000,    3600),
    ('MSC', 'MasterCam',                                1530,    2040,    2448,    3060,    4080,    4896),
    ('FED', 'Front-end Development Course',              960,    1200,    1440,    1920,    2400,    2880),
    ('SPP', 'Solar Professional with Pv Syst',          1620,    2160,    2592,    3240,    4320,    5184),
    ('ARC', 'ArchiCAD',                                 1665,    2220,    2664,    3330,    4440,    5328),
    ('FCP', 'Fortinet FCP Fortigate',                   1485,    1980,    2376,    2970,    3960,    4752),
    ('CAT', 'Catia Course',                             1665,    2220,    2664,    3330,    4440,    5328),
    ('ENS', 'Enscape Course',                           1056,    1320,    1584,    2112,    2640,    3168),
]

# AGI code is duplicated in source data — match these two by name instead
AGI_PRICES = [
    ('ESRI ARC-GIS',  7200,  9600, 11520, 14400, 19200, 23040),
    ('Open-GIS',      5400,  7200,  8640, 10800, 14400, 17280),
]


def set_prices(apps, schema_editor):
    Course = apps.get_model('invoices', 'Course')
    updated = 0

    for code, _name, oo_i, oo_p, oo_a, pr_i, pr_p, pr_a in PRICES:
        n = Course.objects.filter(code=code).update(
            oo_intermediate=Decimal(str(oo_i)),
            oo_professional=Decimal(str(oo_p)),
            oo_advanced=Decimal(str(oo_a)),
            priv_intermediate=Decimal(str(pr_i)),
            priv_professional=Decimal(str(pr_p)),
            priv_advanced=Decimal(str(pr_a)),
        )
        updated += n

    for name_fragment, oo_i, oo_p, oo_a, pr_i, pr_p, pr_a in AGI_PRICES:
        n = Course.objects.filter(name__icontains=name_fragment.split()[0]).update(
            oo_intermediate=Decimal(str(oo_i)),
            oo_professional=Decimal(str(oo_p)),
            oo_advanced=Decimal(str(oo_a)),
            priv_intermediate=Decimal(str(pr_i)),
            priv_professional=Decimal(str(pr_p)),
            priv_advanced=Decimal(str(pr_a)),
        )
        updated += n


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0055_quotation_coupon'),
    ]

    operations = [
        migrations.RunPython(set_prices, noop),
    ]
