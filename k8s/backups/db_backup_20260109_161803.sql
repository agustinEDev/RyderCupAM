--
-- PostgreSQL database dump
--

\restrict 64J7PDDaKKVwgT1pjFqSIqEAdbwwJBH4lNDoS0hactlwjCKitvG91ueZCNkaUJu

-- Dumped from database version 15.15 (Debian 15.15-1.pgdg13+1)
-- Dumped by pg_dump version 15.15 (Debian 15.15-1.pgdg13+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: rydercupam_adminuser
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


ALTER TABLE public.alembic_version OWNER TO rydercupam_adminuser;

--
-- Name: competitions; Type: TABLE; Schema: public; Owner: rydercupam_adminuser
--

CREATE TABLE public.competitions (
    id character(36) NOT NULL,
    creator_id character(36) NOT NULL,
    name character varying(200) NOT NULL,
    start_date date NOT NULL,
    end_date date NOT NULL,
    country_code character(2) NOT NULL,
    secondary_country_code character(2),
    tertiary_country_code character(2),
    team_1_name character varying(100) NOT NULL,
    team_2_name character varying(100) NOT NULL,
    handicap_type character varying(20) NOT NULL,
    handicap_value integer,
    max_players integer DEFAULT 24 NOT NULL,
    team_assignment character varying(20) DEFAULT '''MANUAL'''::character varying NOT NULL,
    status character varying(20) DEFAULT '''DRAFT'''::character varying NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


ALTER TABLE public.competitions OWNER TO rydercupam_adminuser;

--
-- Name: countries; Type: TABLE; Schema: public; Owner: rydercupam_adminuser
--

CREATE TABLE public.countries (
    code character(2) NOT NULL,
    active boolean DEFAULT true NOT NULL,
    name_en character varying(100) NOT NULL,
    name_es character varying(100) NOT NULL
);


ALTER TABLE public.countries OWNER TO rydercupam_adminuser;

--
-- Name: country_adjacencies; Type: TABLE; Schema: public; Owner: rydercupam_adminuser
--

CREATE TABLE public.country_adjacencies (
    country_code_1 character(2) NOT NULL,
    country_code_2 character(2) NOT NULL
);


ALTER TABLE public.country_adjacencies OWNER TO rydercupam_adminuser;

--
-- Name: enrollments; Type: TABLE; Schema: public; Owner: rydercupam_adminuser
--

CREATE TABLE public.enrollments (
    id character(36) NOT NULL,
    competition_id character(36) NOT NULL,
    user_id character(36) NOT NULL,
    status character varying(20) NOT NULL,
    team_id character varying(10),
    custom_handicap numeric(4,1),
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


ALTER TABLE public.enrollments OWNER TO rydercupam_adminuser;

--
-- Name: password_history; Type: TABLE; Schema: public; Owner: rydercupam_adminuser
--

CREATE TABLE public.password_history (
    id character(36) NOT NULL,
    user_id character(36) NOT NULL,
    password_hash character varying(255) NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


ALTER TABLE public.password_history OWNER TO rydercupam_adminuser;

--
-- Name: TABLE password_history; Type: COMMENT; Schema: public; Owner: rydercupam_adminuser
--

COMMENT ON TABLE public.password_history IS 'Historial de contraseñas para prevenir reutilización (últimas 5, máx 1 año)';


--
-- Name: refresh_tokens; Type: TABLE; Schema: public; Owner: rydercupam_adminuser
--

CREATE TABLE public.refresh_tokens (
    id character varying(36) NOT NULL,
    user_id character varying(36) NOT NULL,
    token_hash character varying(64) NOT NULL,
    expires_at timestamp without time zone NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    revoked boolean DEFAULT false NOT NULL,
    revoked_at timestamp without time zone
);


ALTER TABLE public.refresh_tokens OWNER TO rydercupam_adminuser;

--
-- Name: users; Type: TABLE; Schema: public; Owner: rydercupam_adminuser
--

CREATE TABLE public.users (
    id character(36) NOT NULL,
    first_name character varying(50) NOT NULL,
    last_name character varying(50) NOT NULL,
    email character varying(255) NOT NULL,
    password character varying(255) NOT NULL,
    handicap double precision,
    handicap_updated_at timestamp without time zone,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL,
    email_verified boolean DEFAULT false NOT NULL,
    verification_token character varying(255),
    country_code character(2),
    password_reset_token character varying(255),
    reset_token_expires_at timestamp without time zone,
    failed_login_attempts integer DEFAULT 0 NOT NULL,
    locked_until timestamp without time zone
);


ALTER TABLE public.users OWNER TO rydercupam_adminuser;

--
-- Name: COLUMN users.password_reset_token; Type: COMMENT; Schema: public; Owner: rydercupam_adminuser
--

COMMENT ON COLUMN public.users.password_reset_token IS 'Token de reseteo de contraseña (válido 24h, uso único)';


--
-- Name: COLUMN users.reset_token_expires_at; Type: COMMENT; Schema: public; Owner: rydercupam_adminuser
--

COMMENT ON COLUMN public.users.reset_token_expires_at IS 'Fecha de expiración del token de reseteo (24h desde generación)';


--
-- Name: COLUMN users.failed_login_attempts; Type: COMMENT; Schema: public; Owner: rydercupam_adminuser
--

COMMENT ON COLUMN public.users.failed_login_attempts IS 'Contador de intentos fallidos de login (resetea en login exitoso)';


--
-- Name: COLUMN users.locked_until; Type: COMMENT; Schema: public; Owner: rydercupam_adminuser
--

COMMENT ON COLUMN public.users.locked_until IS 'Timestamp hasta cuándo está bloqueada la cuenta (NULL = no bloqueada)';


--
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: rydercupam_adminuser
--

COPY public.alembic_version (version_num) FROM stdin;
d850bb7f327d
\.


--
-- Data for Name: competitions; Type: TABLE DATA; Schema: public; Owner: rydercupam_adminuser
--

COPY public.competitions (id, creator_id, name, start_date, end_date, country_code, secondary_country_code, tertiary_country_code, team_1_name, team_2_name, handicap_type, handicap_value, max_players, team_assignment, status, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: countries; Type: TABLE DATA; Schema: public; Owner: rydercupam_adminuser
--

COPY public.countries (code, active, name_en, name_es) FROM stdin;
AF	t	Afghanistan	Afganistán
AL	t	Albania	Albania
DZ	t	Algeria	Argelia
AD	t	Andorra	Andorra
AO	t	Angola	Angola
AR	t	Argentina	Argentina
AM	t	Armenia	Armenia
AT	t	Austria	Austria
AU	t	Australia	Australia
AZ	t	Azerbaijan	Azerbaiyán
BD	t	Bangladesh	Bangladés
BY	t	Belarus	Bielorrusia
BE	t	Belgium	Bélgica
BZ	t	Belize	Belice
BJ	t	Benin	Benín
BT	t	Bhutan	Bután
BO	t	Bolivia	Bolivia
BA	t	Bosnia and Herzegovina	Bosnia y Herzegovina
BW	t	Botswana	Botsuana
BR	t	Brazil	Brasil
BG	t	Bulgaria	Bulgaria
BF	t	Burkina Faso	Burkina Faso
BI	t	Burundi	Burundi
AG	t	Antigua and Barbuda	Antigua y Barbuda
BS	t	Bahamas	Bahamas
BH	t	Bahrain	Baréin
BB	t	Barbados	Barbados
CV	t	Cabo Verde	Cabo Verde
KM	t	Comoros	Comoras
CG	t	Congo	Congo
GD	t	Grenada	Granada
MT	t	Malta	Malta
MH	t	Marshall Islands	Islas Marshall
MU	t	Mauritius	Mauricio
FM	t	Micronesia	Micronesia
NR	t	Nauru	Nauru
PW	t	Palau	Palaos
KN	t	Saint Kitts and Nevis	San Cristóbal y Nieves
LC	t	Saint Lucia	Santa Lucía
VC	t	Saint Vincent and the Grenadines	San Vicente y las Granadinas
ST	t	Sao Tome and Principe	Santo Tomé y Príncipe
SC	t	Seychelles	Seychelles
SB	t	Solomon Islands	Islas Salomón
KH	t	Cambodia	Camboya
KI	t	Kiribati	Kiribati
CM	t	Cameroon	Camerún
CA	t	Canada	Canadá
CF	t	Central African Republic	República Centroafricana
TD	t	Chad	Chad
CL	t	Chile	Chile
CN	t	China	China
CO	t	Colombia	Colombia
CD	t	Democratic Republic of the Congo	República Democrática del Congo
CR	t	Costa Rica	Costa Rica
CI	t	Côte d'Ivoire	Costa de Marfil
HR	t	Croatia	Croacia
CU	t	Cuba	Cuba
CY	t	Cyprus	Chipre
CZ	t	Czechia	Chequia
DK	t	Denmark	Dinamarca
DJ	t	Djibouti	Yibuti
DO	t	Dominican Republic	República Dominicana
EC	t	Ecuador	Ecuador
EG	t	Egypt	Egipto
SV	t	El Salvador	El Salvador
GQ	t	Equatorial Guinea	Guinea Ecuatorial
ER	t	Eritrea	Eritrea
EE	t	Estonia	Estonia
ET	t	Ethiopia	Etiopía
FI	t	Finland	Finlandia
FJ	t	Fiji	Fiyi
FR	t	France	Francia
GA	t	Gabon	Gabón
GM	t	Gambia	Gambia
GE	t	Georgia	Georgia
DE	t	Germany	Alemania
GH	t	Ghana	Ghana
GR	t	Greece	Grecia
GT	t	Guatemala	Guatemala
GN	t	Guinea	Guinea
GW	t	Guinea-Bissau	Guinea-Bissau
GY	t	Guyana	Guyana
HT	t	Haiti	Haití
HN	t	Honduras	Honduras
HU	t	Hungary	Hungría
IN	t	India	India
ID	t	Indonesia	Indonesia
IR	t	Iran	Irán
IQ	t	Iraq	Irak
IE	t	Ireland	Irlanda
IL	t	Israel	Israel
IS	t	Iceland	Islandia
IT	t	Italy	Italia
JP	t	Japan	Japón
JO	t	Jordan	Jordania
KZ	t	Kazakhstan	Kazajistán
KA	t	Kazakhstan (Alt)	Kazajistán (Alt)
KE	t	Kenya	Kenia
KP	t	North Korea	Corea del Norte
KR	t	South Korea	Corea del Sur
XK	t	Kosovo	Kosovo
KW	t	Kuwait	Kuwait
KG	t	Kyrgyzstan	Kirguistán
LA	t	Laos	Laos
LV	t	Latvia	Letonia
LB	t	Lebanon	Líbano
LS	t	Lesotho	Lesoto
LR	t	Liberia	Liberia
LY	t	Libya	Libia
LI	t	Liechtenstein	Liechtenstein
LT	t	Lithuania	Lituania
LU	t	Luxembourg	Luxemburgo
MK	t	North Macedonia	Macedonia del Norte
MG	t	Madagascar	Madagascar
MW	t	Malawi	Malaui
MY	t	Malaysia	Malasia
MV	t	Maldives	Maldivas
ML	t	Mali	Malí
MR	t	Mauritania	Mauritania
MX	t	Mexico	México
MD	t	Moldova	Moldavia
MC	t	Monaco	Mónaco
MN	t	Mongolia	Mongolia
ME	t	Montenegro	Montenegro
MA	t	Morocco	Marruecos
MZ	t	Mozambique	Mozambique
MM	t	Myanmar	Myanmar
NA	t	Namibia	Namibia
NP	t	Nepal	Nepal
NL	t	Netherlands	Países Bajos
NZ	t	New Zealand	Nueva Zelanda
NI	t	Nicaragua	Nicaragua
NE	t	Niger	Níger
NG	t	Nigeria	Nigeria
NO	t	Norway	Noruega
OM	t	Oman	Omán
PK	t	Pakistan	Pakistán
PA	t	Panama	Panamá
PG	t	Papua New Guinea	Papúa Nueva Guinea
PY	t	Paraguay	Paraguay
PE	t	Peru	Perú
PH	t	Philippines	Filipinas
PL	t	Poland	Polonia
PT	t	Portugal	Portugal
QA	t	Qatar	Catar
RO	t	Romania	Rumania
RU	t	Russia	Rusia
RW	t	Rwanda	Ruanda
SM	t	San Marino	San Marino
SA	t	Saudi Arabia	Arabia Saudita
SN	t	Senegal	Senegal
RS	t	Serbia	Serbia
SL	t	Sierra Leone	Sierra Leona
SK	t	Slovakia	Eslovaquia
SI	t	Slovenia	Eslovenia
SO	t	Somalia	Somalia
ZA	t	South Africa	Sudáfrica
SS	t	South Sudan	Sudán del Sur
ES	t	Spain	España
LK	t	Sri Lanka	Sri Lanka
SD	t	Sudan	Sudán
SR	t	Suriname	Surinam
SZ	t	Eswatini	Esuatini
SE	t	Sweden	Suecia
CH	t	Switzerland	Suiza
SY	t	Syria	Siria
TJ	t	Tajikistan	Tayikistán
TZ	t	Tanzania	Tanzania
TH	t	Thailand	Tailandia
TK	t	Tokelau	Tokelau
TG	t	Togo	Togo
TL	t	Timor-Leste	Timor Oriental
TT	t	Trinidad and Tobago	Trinidad y Tobago
TV	t	Tuvalu	Tuvalu
TN	t	Tunisia	Túnez
TO	t	Tonga	Tonga
TR	t	Turkey	Turquía
TM	t	Turkmenistan	Turkmenistán
UG	t	Uganda	Uganda
UA	t	Ukraine	Ucrania
AE	t	United Arab Emirates	Emiratos Árabes Unidos
GB	t	United Kingdom	Reino Unido
US	t	United States	Estados Unidos
UY	t	Uruguay	Uruguay
UZ	t	Uzbekistan	Uzbekistán
VA	t	Vatican City	Ciudad del Vaticano
VE	t	Venezuela	Venezuela
VU	t	Vanuatu	Vanuatu
VN	t	Vietnam	Vietnam
WF	t	Wallis and Futuna	Wallis y Futuna
WS	t	Samoa	Samoa
YE	t	Yemen	Yemen
ZM	t	Zambia	Zambia
ZW	t	Zimbabwe	Zimbabue
DM	t	Dominica	Dominica
BN	t	Brunei	Brunéi
SG	t	Singapore	Singapur
JM	t	Jamaica	Jamaica
PS	t	Palestine	Palestina
TW	t	Taiwan	Taiwán
\.


--
-- Data for Name: country_adjacencies; Type: TABLE DATA; Schema: public; Owner: rydercupam_adminuser
--

COPY public.country_adjacencies (country_code_1, country_code_2) FROM stdin;
AF	CN
CN	AF
AF	IR
IR	AF
AF	PK
PK	AF
AF	TJ
TJ	AF
AF	TM
TM	AF
AF	UZ
UZ	AF
AL	GR
GR	AL
AL	MK
MK	AL
AL	ME
ME	AL
AL	XK
XK	AL
DZ	LY
LY	DZ
DZ	ML
ML	DZ
DZ	MR
MR	DZ
DZ	MA
MA	DZ
DZ	NE
NE	DZ
DZ	TN
TN	DZ
AD	FR
FR	AD
AD	ES
ES	AD
AO	CG
CG	AO
AO	NA
NA	AO
AO	ZM
ZM	AO
AR	BO
BO	AR
AR	BR
BR	AR
AR	CL
CL	AR
AR	PY
PY	AR
AR	UY
UY	AR
AM	AZ
AZ	AM
AM	GE
GE	AM
AM	IR
IR	AM
AM	TR
TR	AM
AT	CZ
CZ	AT
AT	DE
DE	AT
AT	HU
HU	AT
AT	IT
IT	AT
AT	LI
LI	AT
AT	SK
SK	AT
AT	SI
SI	AT
AZ	IR
IR	AZ
AZ	RU
RU	AZ
AZ	TR
TR	AZ
BD	IN
IN	BD
BD	MM
MM	BD
BY	LV
LV	BY
BY	LT
LT	BY
BY	PL
PL	BY
BY	RU
RU	BY
BY	UA
UA	BY
BE	FR
FR	BE
BE	DE
DE	BE
BE	LU
LU	BE
BE	NL
NL	BE
BZ	GT
GT	BZ
BZ	MX
MX	BZ
BJ	BF
BF	BJ
BJ	NE
NE	BJ
BJ	NG
NG	BJ
BJ	TG
TG	BJ
BT	CN
CN	BT
BT	IN
IN	BT
BO	BR
BR	BO
BO	CL
CL	BO
BO	PY
PY	BO
BO	PE
PE	BO
BA	HR
HR	BA
BA	ME
ME	BA
BA	RS
RS	BA
BW	NA
NA	BW
BW	ZA
ZA	BW
BW	ZM
ZM	BW
BR	CO
CO	BR
BR	FR
FR	BR
BR	GY
GY	BR
BR	PE
PE	BR
BR	PY
PY	BR
BR	SR
SR	BR
BR	UY
UY	BR
BR	VE
VE	BR
BG	GR
GR	BG
BG	MK
MK	BG
BG	RO
RO	BG
BG	RS
RS	BG
BG	TR
TR	BG
BF	CI
CI	BF
BF	GH
GH	BF
BF	ML
ML	BF
BF	NE
NE	BF
BF	TG
TG	BF
BI	RW
RW	BI
BI	TZ
TZ	BI
KH	LA
LA	KH
KH	TH
TH	KH
KH	VN
VN	KH
CM	CF
CF	CM
CM	TD
TD	CM
CM	CG
CG	CM
CM	GQ
GQ	CM
CM	GA
GA	CM
CM	NG
NG	CM
CA	US
US	CA
CF	TD
TD	CF
CF	CG
CG	CF
CF	NG
NG	CF
CF	SS
SS	CF
CF	SD
SD	CF
TD	LY
LY	TD
TD	NE
NE	TD
TD	NG
NG	TD
TD	SS
SS	TD
TD	SD
SD	TD
CL	PE
PE	CL
CN	IN
IN	CN
CN	JP
JP	CN
CN	KR
KR	CN
CN	KZ
KZ	CN
CN	KP
KP	CN
CN	KG
KG	CN
CN	LA
LA	CN
CN	MN
MN	CN
CN	MM
MM	CN
CN	NP
NP	CN
CN	PH
PH	CN
CN	PK
PK	CN
CN	RU
RU	CN
CN	TJ
TJ	CN
CN	TM
TM	CN
CN	TW
TW	CN
CN	UZ
UZ	CN
CN	VN
VN	CN
CO	EC
EC	CO
CO	PA
PA	CO
CO	PE
PE	CO
CO	VE
VE	CO
CG	CD
CD	CG
CG	GA
GA	CG
CG	NG
NG	CG
CR	NI
NI	CR
CR	PA
PA	CR
CI	GH
GH	CI
CI	GN
GN	CI
CI	LR
LR	CI
CI	ML
ML	CI
HR	HU
HU	HR
HR	ME
ME	HR
HR	RS
RS	HR
HR	SI
SI	HR
CU	US
US	CU
CZ	DE
DE	CZ
CZ	PL
PL	CZ
CZ	SK
SK	CZ
CD	AO
AO	CD
CD	BI
BI	CD
CD	BW
BW	CD
CD	MW
MW	CD
CD	NG
NG	CD
CD	RW
RW	CD
CD	TZ
TZ	CD
CD	UG
UG	CD
CD	ZM
ZM	CD
CD	ZW
ZW	CD
DK	DE
DE	DK
DJ	ER
ER	DJ
DJ	ET
ET	DJ
DJ	SO
SO	DJ
DO	HT
HT	DO
EC	PE
PE	EC
EG	IL
IL	EG
EG	JO
JO	EG
EG	LY
LY	EG
EG	PS
PS	EG
EG	SA
SA	EG
EG	SD
SD	EG
SV	GT
GT	SV
SV	HN
HN	SV
ER	ET
ET	ER
ER	SD
SD	ER
ER	SO
SO	ER
EE	LV
LV	EE
EE	RU
RU	EE
ET	KE
KE	ET
ET	SD
SD	ET
ET	SO
SO	ET
ET	SS
SS	ET
ET	TZ
TZ	ET
ET	UG
UG	ET
FI	NO
NO	FI
FI	SE
SE	FI
FI	RU
RU	FI
FR	DE
DE	FR
FR	DM
DM	FR
FR	IT
IT	FR
FR	LU
LU	FR
FR	MC
MC	FR
FR	NL
NL	FR
FR	SM
SM	FR
FR	CH
CH	FR
FR	WF
WF	FR
GA	GQ
GQ	GA
GA	NG
NG	GA
GB	CY
CY	GB
GB	FR
FR	GB
GB	IE
IE	GB
GM	SN
SN	GM
GE	RU
RU	GE
GE	TR
TR	GE
DE	LU
LU	DE
DE	NL
NL	DE
DE	PL
PL	DE
DE	CH
CH	DE
GH	TG
TG	GH
GR	MK
MK	GR
GR	TR
TR	GR
GT	HN
HN	GT
GT	MX
MX	GT
GN	GW
GW	GN
GN	LR
LR	GN
GN	ML
ML	GN
GN	SN
SN	GN
GN	SL
SL	GN
GW	SN
SN	GW
GY	SR
SR	GY
GY	VE
VE	GY
HT	JM
JM	HT
HN	NI
NI	HN
HU	RO
RO	HU
HU	RS
RS	HU
HU	SK
SK	HU
HU	SI
SI	HU
HU	UA
UA	HU
IN	MM
MM	IN
IN	NP
NP	IN
IN	PK
PK	IN
IR	IQ
IQ	IR
IR	PK
PK	IR
IR	TR
TR	IR
IR	JO
JO	IR
IR	KW
KW	IR
IR	SA
SA	IR
IR	SY
SY	IR
IR	TM
TM	IR
IQ	JO
JO	IQ
IQ	KW
KW	IQ
IQ	SA
SA	IQ
IQ	SY
SY	IQ
IQ	TR
TR	IQ
IL	JO
JO	IL
IL	LB
LB	IL
IL	PS
PS	IL
IL	SY
SY	IL
IT	SM
SM	IT
IT	SI
SI	IT
IT	CH
CH	IT
IT	VA
VA	IT
JO	SA
SA	JO
JO	PS
PS	JO
JO	SY
SY	JO
KZ	KG
KG	KZ
KZ	RU
RU	KZ
KZ	TM
TM	KZ
KZ	UZ
UZ	KZ
KE	SO
SO	KE
KE	SS
SS	KE
KE	TZ
TZ	KE
KE	UG
UG	KE
KE	SD
SD	KE
KP	KR
KR	KP
KP	RU
RU	KP
KG	TJ
TJ	KG
KG	UZ
UZ	KG
LA	MM
MM	LA
LA	TH
TH	LA
LA	VN
VN	LA
LV	LT
LT	LV
LV	RU
RU	LV
LB	SY
SY	LB
LR	SL
SL	LR
LY	NE
NE	LY
LY	SD
SD	LY
LY	TN
TN	LY
LI	CH
CH	LI
LT	PL
PL	LT
LT	RU
RU	LT
MK	RS
RS	MK
MK	XK
XK	MK
MW	MZ
MZ	MW
MW	TZ
TZ	MW
MW	ZM
ZM	MW
MY	ID
ID	MY
MY	BN
BN	MY
MY	SG
SG	MY
MY	TH
TH	MY
ML	MR
MR	ML
ML	NE
NE	ML
ML	SN
SN	ML
MR	SN
SN	MR
MX	US
US	MX
MD	RO
RO	MD
MD	UA
UA	MD
MN	RU
RU	MN
ME	RS
RS	ME
ME	XK
XK	ME
MZ	ZA
ZA	MZ
MZ	SZ
SZ	MZ
MZ	TZ
TZ	MZ
MZ	MG
MG	MZ
MZ	ZW
ZW	MZ
MM	TH
TH	MM
NA	ZA
ZA	NA
NA	ZM
ZM	NA
NE	TG
TG	NE
NE	NG
NG	NE
NO	SE
SE	NO
NO	RU
RU	NO
OM	SA
SA	OM
OM	YE
YE	OM
PG	ID
ID	PG
PL	RU
RU	PL
PL	SK
SK	PL
PL	UA
UA	PL
PT	ES
ES	PT
QA	SA
SA	QA
RO	RS
RS	RO
RO	UA
UA	RO
RU	JP
JP	RU
RU	UA
UA	RU
RW	TZ
TZ	RW
RW	UG
UG	RW
SA	KW
KW	SA
SA	YE
YE	SA
SK	UA
UA	SK
ZA	SZ
SZ	ZA
ZA	ZW
ZW	ZA
SS	SD
SD	SS
SS	UG
UG	SS
ES	FR
FR	ES
TJ	UZ
UZ	TJ
TZ	UG
UG	TZ
TZ	ZW
ZW	TZ
TZ	ZM
ZM	TZ
TM	UZ
UZ	TM
UG	SD
SD	UG
ZM	ZW
ZW	ZM
FJ	VU
VU	FJ
GQ	NG
NG	GQ
ID	SR
SR	ID
ID	TL
TL	ID
JP	KR
KR	JP
KA	UZ
UZ	KA
KI	TV
TV	KI
NZ	TK
TK	NZ
SY	TR
TR	SY
SZ	ZW
ZW	SZ
TO	WS
WS	TO
ES	MA
MA	ES
FR	SR
SR	FR
CY	TR
TR	CY
AU	NZ
NZ	AU
IT	HR
HR	IT
VN	PH
PH	VN
\.


--
-- Data for Name: enrollments; Type: TABLE DATA; Schema: public; Owner: rydercupam_adminuser
--

COPY public.enrollments (id, competition_id, user_id, status, team_id, custom_handicap, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: password_history; Type: TABLE DATA; Schema: public; Owner: rydercupam_adminuser
--

COPY public.password_history (id, user_id, password_hash, created_at) FROM stdin;
\.


--
-- Data for Name: refresh_tokens; Type: TABLE DATA; Schema: public; Owner: rydercupam_adminuser
--

COPY public.refresh_tokens (id, user_id, token_hash, expires_at, created_at, revoked, revoked_at) FROM stdin;
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: rydercupam_adminuser
--

COPY public.users (id, first_name, last_name, email, password, handicap, handicap_updated_at, created_at, updated_at, email_verified, verification_token, country_code, password_reset_token, reset_token_expires_at, failed_login_attempts, locked_until) FROM stdin;
\.


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: rydercupam_adminuser
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: competitions competitions_pkey; Type: CONSTRAINT; Schema: public; Owner: rydercupam_adminuser
--

ALTER TABLE ONLY public.competitions
    ADD CONSTRAINT competitions_pkey PRIMARY KEY (id);


--
-- Name: countries countries_pkey; Type: CONSTRAINT; Schema: public; Owner: rydercupam_adminuser
--

ALTER TABLE ONLY public.countries
    ADD CONSTRAINT countries_pkey PRIMARY KEY (code);


--
-- Name: country_adjacencies country_adjacencies_pkey; Type: CONSTRAINT; Schema: public; Owner: rydercupam_adminuser
--

ALTER TABLE ONLY public.country_adjacencies
    ADD CONSTRAINT country_adjacencies_pkey PRIMARY KEY (country_code_1, country_code_2);


--
-- Name: enrollments enrollments_pkey; Type: CONSTRAINT; Schema: public; Owner: rydercupam_adminuser
--

ALTER TABLE ONLY public.enrollments
    ADD CONSTRAINT enrollments_pkey PRIMARY KEY (id);


--
-- Name: password_history password_history_pkey; Type: CONSTRAINT; Schema: public; Owner: rydercupam_adminuser
--

ALTER TABLE ONLY public.password_history
    ADD CONSTRAINT password_history_pkey PRIMARY KEY (id);


--
-- Name: refresh_tokens refresh_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: rydercupam_adminuser
--

ALTER TABLE ONLY public.refresh_tokens
    ADD CONSTRAINT refresh_tokens_pkey PRIMARY KEY (id);


--
-- Name: refresh_tokens refresh_tokens_token_hash_key; Type: CONSTRAINT; Schema: public; Owner: rydercupam_adminuser
--

ALTER TABLE ONLY public.refresh_tokens
    ADD CONSTRAINT refresh_tokens_token_hash_key UNIQUE (token_hash);


--
-- Name: enrollments uq_enrollment_competition_user; Type: CONSTRAINT; Schema: public; Owner: rydercupam_adminuser
--

ALTER TABLE ONLY public.enrollments
    ADD CONSTRAINT uq_enrollment_competition_user UNIQUE (competition_id, user_id);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: rydercupam_adminuser
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: rydercupam_adminuser
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: idx_verification_token; Type: INDEX; Schema: public; Owner: rydercupam_adminuser
--

CREATE INDEX idx_verification_token ON public.users USING btree (verification_token);


--
-- Name: ix_competitions_creator_id; Type: INDEX; Schema: public; Owner: rydercupam_adminuser
--

CREATE INDEX ix_competitions_creator_id ON public.competitions USING btree (creator_id);


--
-- Name: ix_competitions_start_date; Type: INDEX; Schema: public; Owner: rydercupam_adminuser
--

CREATE INDEX ix_competitions_start_date ON public.competitions USING btree (start_date);


--
-- Name: ix_competitions_status; Type: INDEX; Schema: public; Owner: rydercupam_adminuser
--

CREATE INDEX ix_competitions_status ON public.competitions USING btree (status);


--
-- Name: ix_enrollments_competition_id; Type: INDEX; Schema: public; Owner: rydercupam_adminuser
--

CREATE INDEX ix_enrollments_competition_id ON public.enrollments USING btree (competition_id);


--
-- Name: ix_enrollments_status; Type: INDEX; Schema: public; Owner: rydercupam_adminuser
--

CREATE INDEX ix_enrollments_status ON public.enrollments USING btree (status);


--
-- Name: ix_enrollments_user_id; Type: INDEX; Schema: public; Owner: rydercupam_adminuser
--

CREATE INDEX ix_enrollments_user_id ON public.enrollments USING btree (user_id);


--
-- Name: ix_password_history_created_at; Type: INDEX; Schema: public; Owner: rydercupam_adminuser
--

CREATE INDEX ix_password_history_created_at ON public.password_history USING btree (created_at);


--
-- Name: ix_password_history_user_created; Type: INDEX; Schema: public; Owner: rydercupam_adminuser
--

CREATE INDEX ix_password_history_user_created ON public.password_history USING btree (user_id, created_at DESC);


--
-- Name: ix_refresh_tokens_expires_at; Type: INDEX; Schema: public; Owner: rydercupam_adminuser
--

CREATE INDEX ix_refresh_tokens_expires_at ON public.refresh_tokens USING btree (expires_at);


--
-- Name: ix_refresh_tokens_token_hash; Type: INDEX; Schema: public; Owner: rydercupam_adminuser
--

CREATE UNIQUE INDEX ix_refresh_tokens_token_hash ON public.refresh_tokens USING btree (token_hash);


--
-- Name: ix_refresh_tokens_user_id; Type: INDEX; Schema: public; Owner: rydercupam_adminuser
--

CREATE INDEX ix_refresh_tokens_user_id ON public.refresh_tokens USING btree (user_id);


--
-- Name: ix_users_country_code; Type: INDEX; Schema: public; Owner: rydercupam_adminuser
--

CREATE INDEX ix_users_country_code ON public.users USING btree (country_code);


--
-- Name: ix_users_locked_until; Type: INDEX; Schema: public; Owner: rydercupam_adminuser
--

CREATE INDEX ix_users_locked_until ON public.users USING btree (locked_until) WHERE (locked_until IS NOT NULL);


--
-- Name: ix_users_password_reset_token; Type: INDEX; Schema: public; Owner: rydercupam_adminuser
--

CREATE UNIQUE INDEX ix_users_password_reset_token ON public.users USING btree (password_reset_token) WHERE (password_reset_token IS NOT NULL);


--
-- Name: ix_users_reset_token_expires_at; Type: INDEX; Schema: public; Owner: rydercupam_adminuser
--

CREATE INDEX ix_users_reset_token_expires_at ON public.users USING btree (reset_token_expires_at) WHERE (reset_token_expires_at IS NOT NULL);


--
-- Name: competitions competitions_country_code_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rydercupam_adminuser
--

ALTER TABLE ONLY public.competitions
    ADD CONSTRAINT competitions_country_code_fkey FOREIGN KEY (country_code) REFERENCES public.countries(code) ON DELETE RESTRICT;


--
-- Name: competitions competitions_creator_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rydercupam_adminuser
--

ALTER TABLE ONLY public.competitions
    ADD CONSTRAINT competitions_creator_id_fkey FOREIGN KEY (creator_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: competitions competitions_secondary_country_code_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rydercupam_adminuser
--

ALTER TABLE ONLY public.competitions
    ADD CONSTRAINT competitions_secondary_country_code_fkey FOREIGN KEY (secondary_country_code) REFERENCES public.countries(code) ON DELETE RESTRICT;


--
-- Name: competitions competitions_tertiary_country_code_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rydercupam_adminuser
--

ALTER TABLE ONLY public.competitions
    ADD CONSTRAINT competitions_tertiary_country_code_fkey FOREIGN KEY (tertiary_country_code) REFERENCES public.countries(code) ON DELETE RESTRICT;


--
-- Name: country_adjacencies country_adjacencies_country_code_1_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rydercupam_adminuser
--

ALTER TABLE ONLY public.country_adjacencies
    ADD CONSTRAINT country_adjacencies_country_code_1_fkey FOREIGN KEY (country_code_1) REFERENCES public.countries(code) ON DELETE CASCADE;


--
-- Name: country_adjacencies country_adjacencies_country_code_2_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rydercupam_adminuser
--

ALTER TABLE ONLY public.country_adjacencies
    ADD CONSTRAINT country_adjacencies_country_code_2_fkey FOREIGN KEY (country_code_2) REFERENCES public.countries(code) ON DELETE CASCADE;


--
-- Name: enrollments enrollments_competition_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rydercupam_adminuser
--

ALTER TABLE ONLY public.enrollments
    ADD CONSTRAINT enrollments_competition_id_fkey FOREIGN KEY (competition_id) REFERENCES public.competitions(id) ON DELETE CASCADE;


--
-- Name: enrollments enrollments_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rydercupam_adminuser
--

ALTER TABLE ONLY public.enrollments
    ADD CONSTRAINT enrollments_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: refresh_tokens fk_refresh_tokens_user_id; Type: FK CONSTRAINT; Schema: public; Owner: rydercupam_adminuser
--

ALTER TABLE ONLY public.refresh_tokens
    ADD CONSTRAINT fk_refresh_tokens_user_id FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: password_history password_history_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rydercupam_adminuser
--

ALTER TABLE ONLY public.password_history
    ADD CONSTRAINT password_history_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: users users_country_code_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rydercupam_adminuser
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_country_code_fkey FOREIGN KEY (country_code) REFERENCES public.countries(code) ON DELETE SET NULL;


--
-- PostgreSQL database dump complete
--

\unrestrict 64J7PDDaKKVwgT1pjFqSIqEAdbwwJBH4lNDoS0hactlwjCKitvG91ueZCNkaUJu

