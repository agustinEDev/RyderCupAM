# -*- coding: utf-8 -*-
"""
Seed data for countries and country_adjacencies tables.

Source: Wikipedia - List of countries and territories by land borders
Date: 2025-11-18 (updated with additional countries and relations)

Total: 202 countries/territories
Total adjacencies: ~750 bidirectional pairs (stored both directions for query performance)
"""

from alembic import op


def seed_countries():
    """
    Inserts all countries with multilanguage support (EN, ES).

    Note: Includes some territories (Kosovo XK, Gaza GZ, Gibraltar GI, Western Sahara EH)
    that have land borders but may not be universally recognized as sovereign countries.
    """
    op.execute("""
        INSERT INTO countries (code, name_en, name_es) VALUES
        ('AF', 'Afghanistan', 'Afganistán'),
        ('AL', 'Albania', 'Albania'),
        ('DZ', 'Algeria', 'Argelia'),
        ('AD', 'Andorra', 'Andorra'),
        ('AO', 'Angola', 'Angola'),
        ('AR', 'Argentina', 'Argentina'),
        ('AM', 'Armenia', 'Armenia'),
        ('AT', 'Austria', 'Austria'),
        ('AU', 'Australia', 'Australia'),
        ('AZ', 'Azerbaijan', 'Azerbaiyán'),
        ('BD', 'Bangladesh', 'Bangladés'),
        ('BY', 'Belarus', 'Bielorrusia'),
        ('BE', 'Belgium', 'Bélgica'),
        ('BZ', 'Belize', 'Belice'),
        ('BJ', 'Benin', 'Benín'),
        ('BT', 'Bhutan', 'Bután'),
        ('BO', 'Bolivia', 'Bolivia'),
        ('BA', 'Bosnia and Herzegovina', 'Bosnia y Herzegovina'),
        ('BW', 'Botswana', 'Botsuana'),
        ('BR', 'Brazil', 'Brasil'),
        ('BG', 'Bulgaria', 'Bulgaria'),
        ('BF', 'Burkina Faso', 'Burkina Faso'),
        ('BI', 'Burundi', 'Burundi'),
        ('AG', 'Antigua and Barbuda', 'Antigua y Barbuda'),
        ('BS', 'Bahamas', 'Bahamas'),
        ('BH', 'Bahrain', 'Baréin'),
        ('BB', 'Barbados', 'Barbados'),
        ('CV', 'Cabo Verde', 'Cabo Verde'),
        ('KM', 'Comoros', 'Comoras'),
        ('CG', 'Congo', 'Congo'),
        ('GD', 'Grenada', 'Granada'),
        ('MT', 'Malta', 'Malta'),
        ('MH', 'Marshall Islands', 'Islas Marshall'),
        ('MU', 'Mauritius', 'Mauricio'),
        ('FM', 'Micronesia', 'Micronesia'),
        ('NR', 'Nauru', 'Nauru'),
        ('PW', 'Palau', 'Palaos'),
        ('KN', 'Saint Kitts and Nevis', 'San Cristóbal y Nieves'),
        ('LC', 'Saint Lucia', 'Santa Lucía'),
        ('VC', 'Saint Vincent and the Grenadines', 'San Vicente y las Granadinas'),
        ('ST', 'Sao Tome and Principe', 'Santo Tomé y Príncipe'),
        ('SC', 'Seychelles', 'Seychelles'),
        ('SB', 'Solomon Islands', 'Islas Salomón'),
        ('KH', 'Cambodia', 'Camboya'),
        ('KI', 'Kiribati', 'Kiribati'),
        ('CM', 'Cameroon', 'Camerún'),
        ('CA', 'Canada', 'Canadá'),
        -- ('CK', 'Cook Islands', 'Islas Cook'),
        ('CF', 'Central African Republic', 'República Centroafricana'),
        ('TD', 'Chad', 'Chad'),
        ('CL', 'Chile', 'Chile'),
        ('CN', 'China', 'China'),
        ('CO', 'Colombia', 'Colombia'),
        ('CG', 'Republic of the Congo', 'República del Congo'),
        ('CD', 'Democratic Republic of the Congo', 'República Democrática del Congo'),
        ('CR', 'Costa Rica', 'Costa Rica'),
        ('CI', 'Côte d''Ivoire', 'Costa de Marfil'),
        ('HR', 'Croatia', 'Croacia'),
        ('CU', 'Cuba', 'Cuba'),
        ('CY', 'Cyprus', 'Chipre'),
        ('CZ', 'Czechia', 'Chequia'),
        ('DK', 'Denmark', 'Dinamarca'),
        ('DJ', 'Djibouti', 'Yibuti'),
        ('DO', 'Dominican Republic', 'República Dominicana'),
        ('EC', 'Ecuador', 'Ecuador'),
        ('EG', 'Egypt', 'Egipto'),
        ('SV', 'El Salvador', 'El Salvador'),
        ('GQ', 'Equatorial Guinea', 'Guinea Ecuatorial'),
        ('ER', 'Eritrea', 'Eritrea'),
        ('EE', 'Estonia', 'Estonia'),
        ('ET', 'Ethiopia', 'Etiopía'),
        ('FI', 'Finland', 'Finlandia'),
        ('FJ', 'Fiji', 'Fiyi'),
        ('FR', 'France', 'Francia'),
        ('GA', 'Gabon', 'Gabón'),
        ('GM', 'Gambia', 'Gambia'),
        ('GE', 'Georgia', 'Georgia'),
        ('DE', 'Germany', 'Alemania'),
        ('GH', 'Ghana', 'Ghana'),
        -- ('GI', 'Gibraltar', 'Gibraltar'),
        ('GR', 'Greece', 'Grecia'),
        ('GT', 'Guatemala', 'Guatemala'),
        ('GN', 'Guinea', 'Guinea'),
        ('GW', 'Guinea-Bissau', 'Guinea-Bissau'),
        ('GY', 'Guyana', 'Guyana'),
        -- ('GZ', 'Gaza Strip', 'Franja de Gaza'),
        ('HT', 'Haiti', 'Haití'),
        ('HN', 'Honduras', 'Honduras'),
        ('HU', 'Hungary', 'Hungría'),
        ('IN', 'India', 'India'),
        ('ID', 'Indonesia', 'Indonesia'),
        ('IR', 'Iran', 'Irán'),
        ('IQ', 'Iraq', 'Irak'),
        ('IE', 'Ireland', 'Irlanda'),
        ('IL', 'Israel', 'Israel'),
        ('IS', 'Iceland', 'Islandia'),
        ('IT', 'Italy', 'Italia'),
        ('JP', 'Japan', 'Japón'),
        ('JO', 'Jordan', 'Jordania'),
        ('KZ', 'Kazakhstan', 'Kazajistán'),
        ('KA', 'Kazakhstan (Alt)', 'Kazajistán (Alt)'),
        ('KE', 'Kenya', 'Kenia'),
        ('KP', 'North Korea', 'Corea del Norte'),
        ('KR', 'South Korea', 'Corea del Sur'),
        ('XK', 'Kosovo', 'Kosovo'),
        ('KW', 'Kuwait', 'Kuwait'),
        ('KG', 'Kyrgyzstan', 'Kirguistán'),
        ('LA', 'Laos', 'Laos'),
        ('LV', 'Latvia', 'Letonia'),
        ('LB', 'Lebanon', 'Líbano'),
        ('LS', 'Lesotho', 'Lesoto'),
        ('LR', 'Liberia', 'Liberia'),
        ('LY', 'Libya', 'Libia'),
        ('LI', 'Liechtenstein', 'Liechtenstein'),
        ('LT', 'Lithuania', 'Lituania'),
        ('LU', 'Luxembourg', 'Luxemburgo'),
        ('MK', 'North Macedonia', 'Macedonia del Norte'),
        ('MG', 'Madagascar', 'Madagascar'),
        ('MW', 'Malawi', 'Malaui'),
        ('MY', 'Malaysia', 'Malasia'),
        ('MV', 'Maldives', 'Maldivas'),
        ('ML', 'Mali', 'Malí'),
        ('MR', 'Mauritania', 'Mauritania'),
        ('MX', 'Mexico', 'México'),
        ('MD', 'Moldova', 'Moldavia'),
        ('MC', 'Monaco', 'Mónaco'),
        ('MN', 'Mongolia', 'Mongolia'),
        ('ME', 'Montenegro', 'Montenegro'),
        ('MA', 'Morocco', 'Marruecos'),
        ('MZ', 'Mozambique', 'Mozambique'),
        ('MM', 'Myanmar', 'Myanmar'),
        ('NA', 'Namibia', 'Namibia'),
        ('NP', 'Nepal', 'Nepal'),
        -- ('NU', 'Niue', 'Niue'),
        ('NL', 'Netherlands', 'Países Bajos'),
        ('NZ', 'New Zealand', 'Nueva Zelanda'),
        ('NI', 'Nicaragua', 'Nicaragua'),
        ('NE', 'Niger', 'Níger'),
        ('NG', 'Nigeria', 'Nigeria'),
        ('NO', 'Norway', 'Noruega'),
        ('OM', 'Oman', 'Omán'),
        ('PK', 'Pakistan', 'Pakistán'),
        ('PA', 'Panama', 'Panamá'),
        ('PG', 'Papua New Guinea', 'Papúa Nueva Guinea'),
        ('PY', 'Paraguay', 'Paraguay'),
        ('PE', 'Peru', 'Perú'),
        ('PH', 'Philippines', 'Filipinas'),
        ('PL', 'Poland', 'Polonia'),
        ('PT', 'Portugal', 'Portugal'),
        ('QA', 'Qatar', 'Catar'),
        ('RO', 'Romania', 'Rumania'),
        ('RU', 'Russia', 'Rusia'),
        ('RW', 'Rwanda', 'Ruanda'),
        ('SM', 'San Marino', 'San Marino'),
        ('SA', 'Saudi Arabia', 'Arabia Saudita'),
        ('SN', 'Senegal', 'Senegal'),
        ('RS', 'Serbia', 'Serbia'),
        ('SL', 'Sierra Leone', 'Sierra Leona'),
        ('SK', 'Slovakia', 'Eslovaquia'),
        ('SI', 'Slovenia', 'Eslovenia'),
        ('SO', 'Somalia', 'Somalia'),
        ('ZA', 'South Africa', 'Sudáfrica'),
        ('SS', 'South Sudan', 'Sudán del Sur'),
        ('ES', 'Spain', 'España'),
        ('LK', 'Sri Lanka', 'Sri Lanka'),
        ('SD', 'Sudan', 'Sudán'),
        ('SR', 'Suriname', 'Surinam'),
        ('SZ', 'Eswatini', 'Esuatini'),
        ('SE', 'Sweden', 'Suecia'),
        ('CH', 'Switzerland', 'Suiza'),
        ('SY', 'Syria', 'Siria'),
        ('TJ', 'Tajikistan', 'Tayikistán'),
        ('TZ', 'Tanzania', 'Tanzania'),
        ('TH', 'Thailand', 'Tailandia'),
        ('TK', 'Tokelau', 'Tokelau'),
        ('TG', 'Togo', 'Togo'),
        ('TL', 'Timor-Leste', 'Timor Oriental'),
        ('TT', 'Trinidad and Tobago', 'Trinidad y Tobago'),
        ('TV', 'Tuvalu', 'Tuvalu'),
        ('TN', 'Tunisia', 'Túnez'),
        ('TO', 'Tonga', 'Tonga'),
        ('TR', 'Turkey', 'Turquía'),
        ('TM', 'Turkmenistan', 'Turkmenistán'),
        ('UG', 'Uganda', 'Uganda'),
        ('UA', 'Ukraine', 'Ucrania'),
        ('AE', 'United Arab Emirates', 'Emiratos Árabes Unidos'),
        ('GB', 'United Kingdom', 'Reino Unido'),
        ('US', 'United States', 'Estados Unidos'),
        ('UY', 'Uruguay', 'Uruguay'),
        ('UZ', 'Uzbekistan', 'Uzbekistán'),
        ('VA', 'Vatican City', 'Ciudad del Vaticano'),
        ('VE', 'Venezuela', 'Venezuela'),
        ('VU', 'Vanuatu', 'Vanuatu'),
        ('VN', 'Vietnam', 'Vietnam'),
        ('WF', 'Wallis and Futuna', 'Wallis y Futuna'),
        ('WS', 'Samoa', 'Samoa'),
        -- ('EH', 'Western Sahara', 'Sáhara Occidental'),
        ('YE', 'Yemen', 'Yemen'),
        ('ZM', 'Zambia', 'Zambia'),
        ('ZW', 'Zimbabwe', 'Zimbabue'),
        -- ('GF', 'French Guiana', 'Guayana Francesa'),
        ('DM', 'Dominica', 'Dominica'),
        -- ('MQ', 'Martinique', 'Martinica'),
        -- ('RE', 'Réunion', 'Reunión'),
        -- ('PM', 'Saint Pierre and Miquelon', 'San Pedro y Miquelón'),
        -- ('GG', 'Guernsey', 'Guernsey'),
        -- ('IM', 'Isle of Man', 'Isla de Man'),
        -- ('JE', 'Jersey', 'Jersey'),
        -- ('FK', 'Falkland Islands', 'Islas Malvinas'),
        -- ('SJ', 'Svalbard', 'Svalbard'),
        ('BN', 'Brunei', 'Brunéi'),
        ('SG', 'Singapore', 'Singapur'),
        ('JM', 'Jamaica', 'Jamaica'),
        ('PS', 'Palestine', 'Palestina'),
        -- ('HK', 'Hong Kong', 'Hong Kong'),
        ('TW', 'Taiwan', 'Taiwán')
        -- ('FO', 'Faroe Islands', 'Islas Feroe'),
        -- ('GL', 'Greenland', 'Groenlandia')
        ON CONFLICT (code) DO NOTHING;
    """)


def seed_country_adjacencies():
    """
    Inserts country adjacencies (land borders).

    Note: Relationships are bidirectional (A-B and B-A both stored)
    to simplify queries. This avoids needing OR conditions like:
    WHERE (country_code_1 = 'ES' OR country_code_2 = 'ES')

    Instead we can simply do:
    WHERE country_code_1 = 'ES'

    Source: Wikipedia - List of countries and territories by land borders
    """
    op.execute("""
        INSERT INTO country_adjacencies (country_code_1, country_code_2) VALUES
        -- Afghanistan (AF)
        ('AF', 'CN'), ('CN', 'AF'),
        ('AF', 'IR'), ('IR', 'AF'),
        ('AF', 'PK'), ('PK', 'AF'),
        ('AF', 'TJ'), ('TJ', 'AF'),
        ('AF', 'TM'), ('TM', 'AF'),
        ('AF', 'UZ'), ('UZ', 'AF'),
        -- Albania (AL)
        ('AL', 'GR'), ('GR', 'AL'),
        ('AL', 'MK'), ('MK', 'AL'),
        ('AL', 'ME'), ('ME', 'AL'),
        ('AL', 'XK'), ('XK', 'AL'),
        -- Algeria (DZ)
        ('DZ', 'LY'), ('LY', 'DZ'),
        ('DZ', 'ML'), ('ML', 'DZ'),
        ('DZ', 'MR'), ('MR', 'DZ'),
        ('DZ', 'MA'), ('MA', 'DZ'),
        ('DZ', 'NE'), ('NE', 'DZ'),
        ('DZ', 'TN'), ('TN', 'DZ'),
        -- ('DZ', 'EH'), ('EH', 'DZ'),
        -- Andorra (AD)
        ('AD', 'FR'), ('FR', 'AD'),
        ('AD', 'ES'), ('ES', 'AD'),
        -- Angola (AO)
        ('AO', 'CG'), ('CG', 'AO'),
        ('AO', 'NA'), ('NA', 'AO'),
        ('AO', 'ZM'), ('ZM', 'AO'),
        -- Argentina (AR)
        ('AR', 'BO'), ('BO', 'AR'),
        ('AR', 'BR'), ('BR', 'AR'),
        ('AR', 'CL'), ('CL', 'AR'),
        ('AR', 'PY'), ('PY', 'AR'),
        ('AR', 'UY'), ('UY', 'AR'),
        -- Armenia (AM)
        ('AM', 'AZ'), ('AZ', 'AM'),
        ('AM', 'GE'), ('GE', 'AM'),
        ('AM', 'IR'), ('IR', 'AM'),
        ('AM', 'TR'), ('TR', 'AM'),
        -- Austria (AT)
        ('AT', 'CZ'), ('CZ', 'AT'),
        ('AT', 'DE'), ('DE', 'AT'),
        ('AT', 'HU'), ('HU', 'AT'),
        ('AT', 'IT'), ('IT', 'AT'),
        ('AT', 'LI'), ('LI', 'AT'),
        ('AT', 'SK'), ('SK', 'AT'),
        ('AT', 'SI'), ('SI', 'AT'),
        -- ('FR', 'MQ'), ('MQ', 'FR'),
        -- ('FR', 'PM'), ('PM', 'FR'),
        -- ('FR', 'RE'), ('RE', 'FR'),
        ('AZ', 'IR'), ('IR', 'AZ'),
        ('AZ', 'RU'), ('RU', 'AZ'),
        ('AZ', 'TR'), ('TR', 'AZ'),
        -- Bangladesh (BD)
        ('BD', 'IN'), ('IN', 'BD'),
        ('BD', 'MM'), ('MM', 'BD'),
        -- Belarus (BY)
        ('BY', 'LV'), ('LV', 'BY'),
        ('BY', 'LT'), ('LT', 'BY'),
        ('BY', 'PL'), ('PL', 'BY'),
        ('BY', 'RU'), ('RU', 'BY'),
        ('BY', 'UA'), ('UA', 'BY'),
        -- Belgium (BE)
        ('BE', 'FR'), ('FR', 'BE'),
        ('BE', 'DE'), ('DE', 'BE'),
        ('BE', 'LU'), ('LU', 'BE'),
        ('BE', 'NL'), ('NL', 'BE'),
        -- Belize (BZ)
        ('BZ', 'GT'), ('GT', 'BZ'),
        ('BZ', 'MX'), ('MX', 'BZ'),
        -- Benin (BJ)
        ('BJ', 'BF'), ('BF', 'BJ'),
        ('BJ', 'NE'), ('NE', 'BJ'),
        ('BJ', 'NG'), ('NG', 'BJ'),
        ('BJ', 'TG'), ('TG', 'BJ'),
        -- Bhutan (BT)
        ('BT', 'CN'), ('CN', 'BT'),
        ('BT', 'IN'), ('IN', 'BT'),
        -- Bolivia (BO)
        ('BO', 'BR'), ('BR', 'BO'),
        ('BO', 'CL'), ('CL', 'BO'),
        ('BO', 'PY'), ('PY', 'BO'),
        ('BO', 'PE'), ('PE', 'BO'),
        -- Bosnia and Herzegovina (BA)
        ('BA', 'HR'), ('HR', 'BA'),
        ('BA', 'ME'), ('ME', 'BA'),
        ('BA', 'RS'), ('RS', 'BA'),
        -- Botswana (BW)
        ('BW', 'NA'), ('NA', 'BW'),
        ('BW', 'ZA'), ('ZA', 'BW'),
        ('BW', 'ZM'), ('ZM', 'BW'),
        -- Brazil (BR)
        ('BR', 'CO'), ('CO', 'BR'),
        ('BR', 'FR'), ('FR', 'BR'),
        -- ('BR', 'GF'), ('GF', 'BR'),
        ('BR', 'GY'), ('GY', 'BR'),
        ('BR', 'PE'), ('PE', 'BR'),
        ('BR', 'PY'), ('PY', 'BR'),
        ('BR', 'SR'), ('SR', 'BR'),
        ('BR', 'UY'), ('UY', 'BR'),
        ('BR', 'VE'), ('VE', 'BR'),
        -- Bulgaria (BG)
        ('BG', 'GR'), ('GR', 'BG'),
        ('BG', 'MK'), ('MK', 'BG'),
        ('BG', 'RO'), ('RO', 'BG'),
        ('BG', 'RS'), ('RS', 'BG'),
        ('BG', 'TR'), ('TR', 'BG'),
        -- Burkina Faso (BF)
        ('BF', 'CI'), ('CI', 'BF'),
        ('BF', 'GH'), ('GH', 'BF'),
        ('BF', 'ML'), ('ML', 'BF'),
        ('BF', 'NE'), ('NE', 'BF'),
        ('BF', 'TG'), ('TG', 'BF'),
        -- Burundi (BI)
        ('BI', 'RW'), ('RW', 'BI'),
        ('BI', 'TZ'), ('TZ', 'BI'),
        -- Cambodia (KH)
        ('KH', 'LA'), ('LA', 'KH'),
        ('KH', 'TH'), ('TH', 'KH'),
        ('KH', 'VN'), ('VN', 'KH'),
        -- Cameroon (CM)
        ('CM', 'CF'), ('CF', 'CM'),
        ('CM', 'TD'), ('TD', 'CM'),
        ('CM', 'CG'), ('CG', 'CM'),
        ('CM', 'GQ'), ('GQ', 'CM'),
        ('CM', 'GA'), ('GA', 'CM'),
        ('CM', 'NG'), ('NG', 'CM'),
        -- Canada (CA)
        -- ADDITION: CA-GL (ya presente en su lista, pero reordenado aquí para claridad)
        ('CA', 'US'), ('US', 'CA'),
        -- Central African Republic (CF)
        ('CF', 'TD'), ('TD', 'CF'),
        ('CF', 'CG'), ('CG', 'CF'),
        ('CF', 'NG'), ('NG', 'CF'),
        ('CF', 'SS'), ('SS', 'CF'),
        ('CF', 'SD'), ('SD', 'CF'),
        -- Chad (TD)
        ('TD', 'LY'), ('LY', 'TD'),
        ('TD', 'NE'), ('NE', 'TD'),
        ('TD', 'NG'), ('NG', 'TD'),
        ('TD', 'SS'), ('SS', 'TD'),
        ('TD', 'SD'), ('SD', 'TD'),
        -- Chile (CL)
        ('CL', 'PE'), ('PE', 'CL'),
        -- China (CN)
        -- ('CN', 'HK'), ('HK', 'CN'),
        ('CN', 'IN'), ('IN', 'CN'),
        ('CN', 'JP'), ('JP', 'CN'),
        ('CN', 'KR'), ('KR', 'CN'),
        ('CN', 'KZ'), ('KZ', 'CN'),
        ('CN', 'KP'), ('KP', 'CN'),
        ('CN', 'KG'), ('KG', 'CN'),
        ('CN', 'LA'), ('LA', 'CN'),
        ('CN', 'MN'), ('MN', 'CN'),
        ('CN', 'MM'), ('MM', 'CN'),
        ('CN', 'NP'), ('NP', 'CN'),
        ('CN', 'PH'), ('PH', 'CN'),
        ('CN', 'PK'), ('PK', 'CN'),
        ('CN', 'RU'), ('RU', 'CN'),
        ('CN', 'TJ'), ('TJ', 'CN'),
        ('CN', 'TM'), ('TM', 'CN'),
        ('CN', 'TW'), ('TW', 'CN'),
        ('CN', 'UZ'), ('UZ', 'CN'),
        ('CN', 'VN'), ('VN', 'CN'),
        -- Colombia (CO)
        ('CO', 'EC'), ('EC', 'CO'),
        ('CO', 'PA'), ('PA', 'CO'),
        ('CO', 'PE'), ('PE', 'CO'),
        ('CO', 'VE'), ('VE', 'CO'),
        -- Republic of the Congo (CG)
        ('CG', 'CD'), ('CD', 'CG'),
        ('CG', 'GA'), ('GA', 'CG'),
        ('CG', 'NG'), ('NG', 'CG'),
        -- Costa Rica (CR)
        ('CR', 'NI'), ('NI', 'CR'),
        ('CR', 'PA'), ('PA', 'CR'),
        -- Côte d'Ivoire (CI)
        ('CI', 'GH'), ('GH', 'CI'),
        ('CI', 'GN'), ('GN', 'CI'),
        ('CI', 'LR'), ('LR', 'CI'),
        ('CI', 'ML'), ('ML', 'CI'),
        -- Croatia (HR)
        ('HR', 'HU'), ('HU', 'HR'),
        ('HR', 'ME'), ('ME', 'HR'),
        ('HR', 'RS'), ('RS', 'HR'),
        ('HR', 'SI'), ('SI', 'HR'),
        -- Cuba (CU)
        ('CU', 'US'), ('US', 'CU'),
        -- Czechia (CZ)
        ('CZ', 'DE'), ('DE', 'CZ'),
        ('CZ', 'PL'), ('PL', 'CZ'),
        ('CZ', 'SK'), ('SK', 'CZ'),
        -- Democratic Republic of the Congo (CD)
        ('CD', 'AO'), ('AO', 'CD'),
        ('CD', 'BI'), ('BI', 'CD'),
        ('CD', 'BW'), ('BW', 'CD'),
        ('CD', 'CG'), ('CG', 'CD'),
        ('CD', 'MW'), ('MW', 'CD'),
        ('CD', 'NG'), ('NG', 'CD'),
        ('CD', 'RW'), ('RW', 'CD'),
        ('CD', 'TZ'), ('TZ', 'CD'),
        ('CD', 'UG'), ('UG', 'CD'),
        ('CD', 'ZM'), ('ZM', 'CD'),
        ('CD', 'ZW'), ('ZW', 'CD'),
        -- Denmark (DK)
        -- ('DK', 'FO'), ('FO', 'DK'),
        ('DK', 'DE'), ('DE', 'DK'),
        -- Djibouti (DJ)
        ('DJ', 'ER'), ('ER', 'DJ'),
        ('DJ', 'ET'), ('ET', 'DJ'),
        ('DJ', 'SO'), ('SO', 'DJ'),
        -- Dominican Republic (DO)
        ('DO', 'HT'), ('HT', 'DO'),
        -- Ecuador (EC)
        ('EC', 'PE'), ('PE', 'EC'),
        -- Egypt (EG)
        ('EG', 'IL'), ('IL', 'EG'),
        ('EG', 'JO'), ('JO', 'EG'),
        ('EG', 'LY'), ('LY', 'EG'),
        ('EG', 'PS'), ('PS', 'EG'),
        ('EG', 'SA'), ('SA', 'EG'),
        ('EG', 'SD'), ('SD', 'EG'),
        -- El Salvador (SV)
        ('SV', 'GT'), ('GT', 'SV'),
        ('SV', 'HN'), ('HN', 'SV'),
        -- Eritrea (ER)
        ('ER', 'ET'), ('ET', 'ER'),
        ('ER', 'SD'), ('SD', 'ER'),
        ('ER', 'SO'), ('SO', 'ER'),
        -- Estonia (EE)
        ('EE', 'LV'), ('LV', 'EE'),
        ('EE', 'RU'), ('RU', 'EE'),
        -- Ethiopia (ET)
        ('ET', 'KE'), ('KE', 'ET'),
        ('ET', 'SD'), ('SD', 'ET'),
        ('ET', 'SO'), ('SO', 'ET'),
        ('ET', 'SS'), ('SS', 'ET'),
        ('ET', 'TZ'), ('TZ', 'ET'),
        ('ET', 'UG'), ('UG', 'ET'),
        -- Finland (FI)
        ('FI', 'NO'), ('NO', 'FI'),
        ('FI', 'SE'), ('SE', 'FI'),
        ('FI', 'RU'), ('RU', 'FI'),
        -- France (FR)
        ('FR', 'DE'), ('DE', 'FR'),
        ('FR', 'DM'), ('DM', 'FR'),
        -- ('FR', 'GF'), ('GF', 'FR'),
        ('FR', 'IT'), ('IT', 'FR'),
        ('FR', 'LU'), ('LU', 'FR'),
        ('FR', 'MC'), ('MC', 'FR'),
        -- ('FR', 'MQ'), ('MQ', 'FR'),  -- MQ (Martinique) no existe en countries
        ('FR', 'NL'), ('NL', 'FR'),
        ('FR', 'PM'), ('PM', 'FR'),
        ('FR', 'RE'), ('RE', 'FR'),
        ('FR', 'SM'), ('SM', 'FR'),
        ('FR', 'CH'), ('CH', 'FR'),
        ('FR', 'WF'), ('WF', 'FR'),
        -- Gabon (GA)
        ('GA', 'GQ'), ('GQ', 'GA'),
        ('GA', 'NG'), ('NG', 'GA'),
        -- United Kingdom (GB)
        ('GB', 'CY'), ('CY', 'GB'),
        -- ('GB', 'FK'), ('FK', 'GB'),
        ('GB', 'FR'), ('FR', 'GB'),
        -- ('GB', 'GG'), ('GG', 'GB'),
        -- ('GB', 'GI'), ('GI', 'GB'),
        ('GB', 'IE'), ('IE', 'GB'),
        -- ('GB', 'IM'), ('IM', 'GB'),
        -- ('GB', 'JE'), ('JE', 'GB'),
        -- Gambia (GM)
        ('GM', 'SN'), ('SN', 'GM'),
        -- Georgia (GE)
        ('GE', 'RU'), ('RU', 'GE'),
        ('GE', 'TR'), ('TR', 'GE'),
        -- Germany (DE)
        ('DE', 'LU'), ('LU', 'DE'),
        ('DE', 'NL'), ('NL', 'DE'),
        ('DE', 'PL'), ('PL', 'DE'),
        ('DE', 'CH'), ('CH', 'DE'),
        -- Ghana (GH)
        ('GH', 'TG'), ('TG', 'GH'),
        -- Greece (GR)
        ('GR', 'MK'), ('MK', 'GR'),
        ('GR', 'TR'), ('TR', 'GR'),
        -- Guatemala (GT)
        ('GT', 'HN'), ('HN', 'GT'),
        ('GT', 'MX'), ('MX', 'GT'),
        -- Guinea (GN)
        ('GN', 'GW'), ('GW', 'GN'),
        ('GN', 'LR'), ('LR', 'GN'),
        ('GN', 'ML'), ('ML', 'GN'),
        ('GN', 'SN'), ('SN', 'GN'),
        ('GN', 'SL'), ('SL', 'GN'),
        -- Guinea-Bissau (GW)
        ('GW', 'SN'), ('SN', 'GW'),
        -- Guyana (GY)
        ('GY', 'SR'), ('SR', 'GY'),
        ('GY', 'VE'), ('VE', 'GY'),
        -- Haiti (HT)
        ('HT', 'JM'), ('JM', 'HT'),
        -- Honduras (HN)
        ('HN', 'NI'), ('NI', 'HN'),
        -- Hungary (HU)
        ('HU', 'RO'), ('RO', 'HU'),
        ('HU', 'RS'), ('RS', 'HU'),
        ('HU', 'SK'), ('SK', 'HU'),
        ('HU', 'SI'), ('SI', 'HU'),
        ('HU', 'UA'), ('UA', 'HU'),
        -- India (IN)
        ('IN', 'MM'), ('MM', 'IN'),
        ('IN', 'NP'), ('NP', 'IN'),
        ('IN', 'PK'), ('PK', 'IN'),
        -- Iran (IR)
        ('IR', 'IQ'), ('IQ', 'IR'),
        ('IR', 'PK'), ('PK', 'IR'),
        ('IR', 'TR'), ('TR', 'IR'),
        ('IR', 'JO'), ('JO', 'IR'),
        ('IR', 'KW'), ('KW', 'IR'),
        ('IR', 'SA'), ('SA', 'IR'),
        ('IR', 'SY'), ('SY', 'IR'),
        ('IR', 'TM'), ('TM', 'IR'),
        -- Iraq (IQ)
        ('IQ', 'JO'), ('JO', 'IQ'),
        ('IQ', 'KW'), ('KW', 'IQ'),
        ('IQ', 'SA'), ('SA', 'IQ'),
        ('IQ', 'SY'), ('SY', 'IQ'),
        ('IQ', 'TR'), ('TR', 'IQ'),
        -- Israel (IL)
        ('IL', 'JO'), ('JO', 'IL'),
        ('IL', 'LB'), ('LB', 'IL'),
        ('IL', 'PS'), ('PS', 'IL'),
        ('IL', 'SY'), ('SY', 'IL'),
        -- Italy (IT)
        ('IT', 'SM'), ('SM', 'IT'),
        ('IT', 'SI'), ('SI', 'IT'),
        ('IT', 'CH'), ('CH', 'IT'),
        ('IT', 'VA'), ('VA', 'IT'),
        -- Jordan (JO)
        ('JO', 'SA'), ('SA', 'JO'),
        ('JO', 'EG'), ('EG', 'JO'),
        ('JO', 'IR'), ('IR', 'JO'),
        ('JO', 'PS'), ('PS', 'JO'),
        ('JO', 'SY'), ('SY', 'JO'),
        -- Kazakhstan (KZ)
        ('KZ', 'KG'), ('KG', 'KZ'),
        ('KZ', 'RU'), ('RU', 'KZ'),
        ('KZ', 'TM'), ('TM', 'KZ'),
        ('KZ', 'UZ'), ('UZ', 'KZ'),
        -- Kenya (KE)
        ('KE', 'SO'), ('SO', 'KE'),
        ('KE', 'SS'), ('SS', 'KE'),
        ('KE', 'TZ'), ('TZ', 'KE'),
        ('KE', 'UG'), ('UG', 'KE'),
        ('KE', 'SD'), ('SD', 'KE'),
        -- North Korea (KP)
        ('KP', 'KR'), ('KR', 'KP'),
        ('KP', 'RU'), ('RU', 'KP'),
        -- Kyrgyzstan (KG)
        ('KG', 'TJ'), ('TJ', 'KG'),
        ('KG', 'UZ'), ('UZ', 'KG'),
        -- Laos (LA)
        ('LA', 'MM'), ('MM', 'LA'),
        ('LA', 'TH'), ('TH', 'LA'),
        ('LA', 'VN'), ('VN', 'LA'),
        -- Latvia (LV)
        ('LV', 'LT'), ('LT', 'LV'),
        ('LV', 'RU'), ('RU', 'LV'),
        -- Lebanon (LB)
        ('LB', 'SY'), ('SY', 'LB'),
        -- Lesotho (LS)
        -- Liberia (LR)
        ('LR', 'SL'), ('SL', 'LR'),
        -- Libya (LY)
        ('LY', 'NE'), ('NE', 'LY'),
        ('LY', 'SD'), ('SD', 'LY'),
        ('LY', 'TN'), ('TN', 'LY'),
        -- Liechtenstein (LI)
        ('LI', 'CH'), ('CH', 'LI'),
        -- Lithuania (LT)
        ('LT', 'PL'), ('PL', 'LT'),
        ('LT', 'RU'), ('RU', 'LT'),
        -- North Macedonia (MK)
        ('MK', 'RS'), ('RS', 'MK'),
        ('MK', 'XK'), ('XK', 'MK'),
        -- Malawi (MW)
        ('MW', 'MZ'), ('MZ', 'MW'),
        ('MW', 'TZ'), ('TZ', 'MW'),
        ('MW', 'ZM'), ('ZM', 'MW'),
        -- Malaysia (MY)
        ('MY', 'ID'), ('ID', 'MY'),
        ('MY', 'BN'), ('BN', 'MY'),
        ('MY', 'SG'), ('SG', 'MY'),
        ('MY', 'TH'), ('TH', 'MY'),
        -- Mali (ML)
        ('ML', 'MR'), ('MR', 'ML'),
        ('ML', 'NE'), ('NE', 'ML'),
        ('ML', 'SN'), ('SN', 'ML'),
        -- Mauritania (MR)
        ('MR', 'SN'), ('SN', 'MR'),
        -- Mexico (MX)
        ('MX', 'US'), ('US', 'MX'),
        -- Moldova (MD)
        ('MD', 'RO'), ('RO', 'MD'),
        ('MD', 'UA'), ('UA', 'MD'),
        -- Mongolia (MN)
        ('MN', 'RU'), ('RU', 'MN'),
        -- Montenegro (ME)
        ('ME', 'RS'), ('RS', 'ME'),
        ('ME', 'XK'), ('XK', 'ME'),
        -- Morocco (MA)
        ('MA', 'EH'), ('EH', 'MA'),
        -- Mozambique (MZ)
        ('MZ', 'ZA'), ('ZA', 'MZ'),
        ('MZ', 'SZ'), ('SZ', 'MZ'),
        ('MZ', 'TZ'), ('TZ', 'MZ'),
        ('MZ', 'MG'), ('MG', 'MZ'),
        ('MZ', 'ZW'), ('ZW', 'MZ'),
        -- Myanmar (MM)
        ('MM', 'TH'), ('TH', 'MM'),
        -- Namibia (NA)
        ('NA', 'ZA'), ('ZA', 'NA'),
        ('NA', 'ZM'), ('ZM', 'NA'),
        -- Niger (NE)
        ('NE', 'TG'), ('TG', 'NE'),
        ('NE', 'NG'), ('NG', 'NE'),
        -- Norway (NO)
        ('NO', 'SE'), ('SE', 'NO'),
        -- ('NO', 'SJ'), ('SJ', 'NO'),  
        ('NO', 'RU'), ('RU', 'NO'),
        -- Oman (OM)
        ('OM', 'SA'), ('SA', 'OM'),
        ('OM', 'YE'), ('YE', 'OM'),
        -- Papua New Guinea (PG)
        ('PG', 'ID'), ('ID', 'PG'),
        -- Poland (PL)
        ('PL', 'RU'), ('RU', 'PL'),
        ('PL', 'SK'), ('SK', 'PL'),
        ('PL', 'UA'), ('UA', 'PL'),
        -- Portugal (PT)
        ('PT', 'ES'), ('ES', 'PT'),
        -- Qatar (QA)
        ('QA', 'SA'), ('SA', 'QA'),
        -- Romania (RO)
        ('RO', 'RS'), ('RS', 'RO'),
        ('RO', 'UA'), ('UA', 'RO'),
        -- Russia (RU)
        ('RU', 'JP'), ('JP', 'RU'),
        ('RU', 'UA'), ('UA', 'RU'),
        -- Rwanda (RW)
        ('RW', 'TZ'), ('TZ', 'RW'),
        ('RW', 'UG'), ('UG', 'RW'),
        -- Saudi Arabia (SA)
        ('SA', 'EG'), ('EG', 'SA'),
        ('SA', 'IR'), ('IR', 'SA'),
        ('SA', 'KW'), ('KW', 'SA'),
        ('SA', 'YE'), ('YE', 'SA'),
        -- Serbia (RS)
        -- Slovakia (SK)
        ('SK', 'UA'), ('UA', 'SK'),
        -- South Africa (ZA)
        ('ZA', 'SZ'), ('SZ', 'ZA'),
        ('ZA', 'ZW'), ('ZW', 'ZA'),
        -- South Sudan (SS)
        ('SS', 'SD'), ('SD', 'SS'),
        ('SS', 'TD'), ('TD', 'SS'),
        ('SS', 'UG'), ('UG', 'SS'),
        -- Spain (ES)
        ('ES', 'FR'), ('FR', 'ES'),
        -- ('ES', 'GI'), ('GI', 'ES'),  
        -- Tajikistan (TJ)
        ('TJ', 'UZ'), ('UZ', 'TJ'),
        -- Tanzania (TZ)
        ('TZ', 'UG'), ('UG', 'TZ'),
        ('TZ', 'ZW'), ('ZW', 'TZ'),
        ('TZ', 'ZM'), ('ZM', 'TZ'),
        -- Turkmenistan (TM)
        ('TM', 'UZ'), ('UZ', 'TM'),
        -- Uganda (UG)
        ('UG', 'ET'), ('ET', 'UG'),
        ('UG', 'SD'), ('SD', 'UG'),
        -- Zambia (ZM)
        ('ZM', 'ZW'), ('ZW', 'ZM'),
        -- Additional relations
        -- ('CK', 'NZ'), ('NZ', 'CK'),
        ('FJ', 'VU'), ('VU', 'FJ'),
        -- ('GL', 'IS'), ('IS', 'GL'),
        ('GQ', 'NG'), ('NG', 'GQ'),
        ('ID', 'SR'), ('SR', 'ID'),
        ('ID', 'TL'), ('TL', 'ID'),
        ('JP', 'KR'), ('KR', 'JP'),
        ('KA', 'UZ'), ('UZ', 'KA'),
        ('KI', 'TV'), ('TV', 'KI'),
        -- ('NU', 'NZ'), ('NZ', 'NU'),
        ('NZ', 'TK'), ('TK', 'NZ'),
        ('SY', 'TR'), ('TR', 'SY'),
        ('SZ', 'ZW'), ('ZW', 'SZ'),
        ('TO', 'WS'), ('WS', 'TO'),
        ('ES', 'MA'), ('MA', 'ES'),
        ('FR', 'SR'), ('SR', 'FR'),
        ('IL', 'PS'), ('PS', 'IL'),
        -- ('CA', 'GL'), ('GL', 'CA'),
        ('CY', 'TR'), ('TR', 'CY'),
        ('AU', 'NZ'), ('NZ', 'AU'),
        ('IT', 'HR'), ('HR', 'IT'),
        ('VN', 'PH'), ('PH', 'VN')
        ON CONFLICT (country_code_1, country_code_2) DO NOTHING;
    """)