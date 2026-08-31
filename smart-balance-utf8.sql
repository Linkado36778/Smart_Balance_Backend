--
-- PostgreSQL database dump
--

\restrict iajnc76aAXqxIaQAJOfYCdJjPboR61uQvDBgtuPqQSYOfZMky2SqstEkNcQDIsR

-- Dumped from database version 18.3
-- Dumped by pg_dump version 18.6

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

ALTER TABLE IF EXISTS ONLY public."User" DROP CONSTRAINT IF EXISTS "User_nutricionist_id_fkey";
ALTER TABLE IF EXISTS ONLY public."User_Allergen" DROP CONSTRAINT IF EXISTS "User_Allergen_user_id_fkey";
ALTER TABLE IF EXISTS ONLY public."User_Allergen" DROP CONSTRAINT IF EXISTS "User_Allergen_allergen_id_fkey";
ALTER TABLE IF EXISTS ONLY public."Meal" DROP CONSTRAINT IF EXISTS "Meal_user_id_fkey";
ALTER TABLE IF EXISTS ONLY public."Meal_Food" DROP CONSTRAINT IF EXISTS "Meal_Food_meal_id_fkey";
ALTER TABLE IF EXISTS ONLY public."Meal_Food" DROP CONSTRAINT IF EXISTS "Meal_Food_food_id_fkey";
ALTER TABLE IF EXISTS ONLY public."Food" DROP CONSTRAINT IF EXISTS "Food_category_id_fkey";
ALTER TABLE IF EXISTS ONLY public."Food" DROP CONSTRAINT IF EXISTS "Food_brand_id_fkey";
ALTER TABLE IF EXISTS ONLY public."Food_Nutrient" DROP CONSTRAINT IF EXISTS "Food_Nutrient_nutrient_id_fkey";
ALTER TABLE IF EXISTS ONLY public."Food_Nutrient" DROP CONSTRAINT IF EXISTS "Food_Nutrient_food_id_fkey";
ALTER TABLE IF EXISTS ONLY public."Allergen_Food" DROP CONSTRAINT IF EXISTS "Allergen_Food_food_id_fkey";
ALTER TABLE IF EXISTS ONLY public."Allergen_Food" DROP CONSTRAINT IF EXISTS "Allergen_Food_allergen_id_fkey";
DROP INDEX IF EXISTS public."ix_User_nutricionist_id";
DROP INDEX IF EXISTS public."ix_User_id";
DROP INDEX IF EXISTS public."ix_User_email";
DROP INDEX IF EXISTS public."ix_Nutrient_unit";
DROP INDEX IF EXISTS public."ix_Nutrient_name";
DROP INDEX IF EXISTS public."ix_Nutrient_id";
DROP INDEX IF EXISTS public."ix_Nutrient_calories_per_unit";
DROP INDEX IF EXISTS public."ix_Nutricionist_phone";
DROP INDEX IF EXISTS public."ix_Nutricionist_password";
DROP INDEX IF EXISTS public."ix_Nutricionist_id";
DROP INDEX IF EXISTS public."ix_Nutricionist_email";
DROP INDEX IF EXISTS public."ix_Meal_user_id";
DROP INDEX IF EXISTS public."ix_Meal_id";
DROP INDEX IF EXISTS public."ix_Food_name";
DROP INDEX IF EXISTS public."ix_Food_id";
DROP INDEX IF EXISTS public."ix_Food_category_id";
DROP INDEX IF EXISTS public."ix_Food_brand_id";
DROP INDEX IF EXISTS public."ix_Category_name";
DROP INDEX IF EXISTS public."ix_Category_id";
DROP INDEX IF EXISTS public."ix_Brand_name";
DROP INDEX IF EXISTS public."ix_Brand_id";
DROP INDEX IF EXISTS public."ix_Allergen_name";
DROP INDEX IF EXISTS public."ix_Allergen_id";
ALTER TABLE IF EXISTS ONLY public."User" DROP CONSTRAINT IF EXISTS "User_pkey";
ALTER TABLE IF EXISTS ONLY public."User_Allergen" DROP CONSTRAINT IF EXISTS "User_Allergen_pkey";
ALTER TABLE IF EXISTS ONLY public."Nutrient" DROP CONSTRAINT IF EXISTS "Nutrient_pkey";
ALTER TABLE IF EXISTS ONLY public."Nutricionist" DROP CONSTRAINT IF EXISTS "Nutricionist_pkey";
ALTER TABLE IF EXISTS ONLY public."Meal" DROP CONSTRAINT IF EXISTS "Meal_pkey";
ALTER TABLE IF EXISTS ONLY public."Meal_Food" DROP CONSTRAINT IF EXISTS "Meal_Food_pkey";
ALTER TABLE IF EXISTS ONLY public."Food" DROP CONSTRAINT IF EXISTS "Food_pkey";
ALTER TABLE IF EXISTS ONLY public."Food_Nutrient" DROP CONSTRAINT IF EXISTS "Food_Nutrient_pkey";
ALTER TABLE IF EXISTS ONLY public."Category" DROP CONSTRAINT IF EXISTS "Category_pkey";
ALTER TABLE IF EXISTS ONLY public."Brand" DROP CONSTRAINT IF EXISTS "Brand_pkey";
ALTER TABLE IF EXISTS ONLY public."Allergen" DROP CONSTRAINT IF EXISTS "Allergen_pkey";
ALTER TABLE IF EXISTS ONLY public."Allergen_Food" DROP CONSTRAINT IF EXISTS "Allergen_Food_pkey";
ALTER TABLE IF EXISTS public."User" ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public."Nutrient" ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public."Nutricionist" ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public."Meal" ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public."Food" ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public."Category" ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public."Brand" ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public."Allergen" ALTER COLUMN id DROP DEFAULT;
DROP SEQUENCE IF EXISTS public."User_id_seq";
DROP TABLE IF EXISTS public."User_Allergen";
DROP TABLE IF EXISTS public."User";
DROP SEQUENCE IF EXISTS public."Nutrient_id_seq";
DROP TABLE IF EXISTS public."Nutrient";
DROP SEQUENCE IF EXISTS public."Nutricionist_id_seq";
DROP TABLE IF EXISTS public."Nutricionist";
DROP SEQUENCE IF EXISTS public."Meal_id_seq";
DROP TABLE IF EXISTS public."Meal_Food";
DROP TABLE IF EXISTS public."Meal";
DROP SEQUENCE IF EXISTS public."Food_id_seq";
DROP TABLE IF EXISTS public."Food_Nutrient";
DROP TABLE IF EXISTS public."Food";
DROP SEQUENCE IF EXISTS public."Category_id_seq";
DROP TABLE IF EXISTS public."Category";
DROP SEQUENCE IF EXISTS public."Brand_id_seq";
DROP TABLE IF EXISTS public."Brand";
DROP SEQUENCE IF EXISTS public."Allergen_id_seq";
DROP TABLE IF EXISTS public."Allergen_Food";
DROP TABLE IF EXISTS public."Allergen";
SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: Allergen; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public."Allergen" (
    id integer NOT NULL,
    name character varying NOT NULL
);


ALTER TABLE public."Allergen" OWNER TO postgres;

--
-- Name: Allergen_Food; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public."Allergen_Food" (
    food_id integer NOT NULL,
    allergen_id integer NOT NULL
);


ALTER TABLE public."Allergen_Food" OWNER TO postgres;

--
-- Name: Allergen_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public."Allergen_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public."Allergen_id_seq" OWNER TO postgres;

--
-- Name: Allergen_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public."Allergen_id_seq" OWNED BY public."Allergen".id;


--
-- Name: Brand; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public."Brand" (
    id integer NOT NULL,
    name character varying NOT NULL
);


ALTER TABLE public."Brand" OWNER TO postgres;

--
-- Name: Brand_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public."Brand_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public."Brand_id_seq" OWNER TO postgres;

--
-- Name: Brand_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public."Brand_id_seq" OWNED BY public."Brand".id;


--
-- Name: Category; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public."Category" (
    id integer NOT NULL,
    name character varying NOT NULL
);


ALTER TABLE public."Category" OWNER TO postgres;

--
-- Name: Category_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public."Category_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public."Category_id_seq" OWNER TO postgres;

--
-- Name: Category_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public."Category_id_seq" OWNED BY public."Category".id;


--
-- Name: Food; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public."Food" (
    id integer NOT NULL,
    name character varying NOT NULL,
    category_id integer,
    brand_id integer,
    image_url character varying
);


ALTER TABLE public."Food" OWNER TO postgres;

--
-- Name: Food_Nutrient; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public."Food_Nutrient" (
    food_id integer NOT NULL,
    nutrient_id integer NOT NULL,
    amount double precision NOT NULL
);


ALTER TABLE public."Food_Nutrient" OWNER TO postgres;

--
-- Name: Food_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public."Food_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public."Food_id_seq" OWNER TO postgres;

--
-- Name: Food_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public."Food_id_seq" OWNED BY public."Food".id;


--
-- Name: Meal; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public."Meal" (
    id integer NOT NULL,
    name character varying NOT NULL,
    calories double precision NOT NULL,
    weight_g double precision NOT NULL,
    consumed_at timestamp without time zone NOT NULL,
    user_id integer NOT NULL
);


ALTER TABLE public."Meal" OWNER TO postgres;

--
-- Name: Meal_Food; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public."Meal_Food" (
    meal_id integer NOT NULL,
    food_id integer NOT NULL
);


ALTER TABLE public."Meal_Food" OWNER TO postgres;

--
-- Name: Meal_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public."Meal_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public."Meal_id_seq" OWNER TO postgres;

--
-- Name: Meal_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public."Meal_id_seq" OWNED BY public."Meal".id;


--
-- Name: Nutricionist; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public."Nutricionist" (
    id integer NOT NULL,
    password character varying NOT NULL,
    created_at timestamp without time zone NOT NULL,
    phone character varying NOT NULL,
    email character varying NOT NULL
);


ALTER TABLE public."Nutricionist" OWNER TO postgres;

--
-- Name: Nutricionist_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public."Nutricionist_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public."Nutricionist_id_seq" OWNER TO postgres;

--
-- Name: Nutricionist_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public."Nutricionist_id_seq" OWNED BY public."Nutricionist".id;


--
-- Name: Nutrient; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public."Nutrient" (
    id integer NOT NULL,
    name character varying NOT NULL,
    unit character varying NOT NULL,
    calories_per_unit double precision
);


ALTER TABLE public."Nutrient" OWNER TO postgres;

--
-- Name: Nutrient_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public."Nutrient_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public."Nutrient_id_seq" OWNER TO postgres;

--
-- Name: Nutrient_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public."Nutrient_id_seq" OWNED BY public."Nutrient".id;


--
-- Name: User; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public."User" (
    id integer NOT NULL,
    password character varying NOT NULL,
    email character varying NOT NULL,
    birthdate timestamp without time zone NOT NULL,
    weight_kg double precision NOT NULL,
    height_m double precision NOT NULL,
    sex character varying NOT NULL,
    created_at timestamp without time zone NOT NULL,
    is_active boolean NOT NULL,
    nutricionist_id integer
);


ALTER TABLE public."User" OWNER TO postgres;

--
-- Name: User_Allergen; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public."User_Allergen" (
    allergen_id integer NOT NULL,
    user_id integer NOT NULL
);


ALTER TABLE public."User_Allergen" OWNER TO postgres;

--
-- Name: User_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public."User_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public."User_id_seq" OWNER TO postgres;

--
-- Name: User_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public."User_id_seq" OWNED BY public."User".id;


--
-- Name: Allergen id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public."Allergen" ALTER COLUMN id SET DEFAULT nextval('public."Allergen_id_seq"'::regclass);


--
-- Name: Brand id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public."Brand" ALTER COLUMN id SET DEFAULT nextval('public."Brand_id_seq"'::regclass);


--
-- Name: Category id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public."Category" ALTER COLUMN id SET DEFAULT nextval('public."Category_id_seq"'::regclass);


--
-- Name: Food id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public."Food" ALTER COLUMN id SET DEFAULT nextval('public."Food_id_seq"'::regclass);


--
-- Name: Meal id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public."Meal" ALTER COLUMN id SET DEFAULT nextval('public."Meal_id_seq"'::regclass);


--
-- Name: Nutricionist id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public."Nutricionist" ALTER COLUMN id SET DEFAULT nextval('public."Nutricionist_id_seq"'::regclass);


--
-- Name: Nutrient id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public."Nutrient" ALTER COLUMN id SET DEFAULT nextval('public."Nutrient_id_seq"'::regclass);


--
-- Name: User id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public."User" ALTER COLUMN id SET DEFAULT nextval('public."User_id_seq"'::regclass);


--
-- Data for Name: Allergen; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public."Allergen" (id, name) FROM stdin;
6	Alfa-Gal
1	Ovomuc├│ide
2	Ovoalbumina
3	Ovotransferrina
4	Lactucopicrina
5	Lactucina 
7	Mal d 1
8	Mal d 2
9	Mal d 3
10	Mal d 4
11	Mus a 1
12	Mus a 2
13	Mus a 3
14	nsLTP
15	Patatina
16	Gal d 1
17	Albumina s├®rica
18	Parvalb├║minas
19	Gliadina
\.


--
-- Data for Name: Allergen_Food; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public."Allergen_Food" (food_id, allergen_id) FROM stdin;
25	19
11	18
11	17
11	16
10	15
9	14
8	13
8	12
8	11
7	10
7	9
7	8
7	7
5	6
4	5
4	4
6	3
6	2
6	1
12	16
12	17
12	18
13	16
13	17
13	18
14	16
14	17
14	18
15	16
15	17
15	18
16	16
16	17
16	18
17	16
17	17
17	18
18	16
18	17
18	18
19	16
19	17
19	18
20	16
20	17
20	18
21	16
21	17
21	18
22	16
22	17
22	18
23	16
23	17
23	18
24	16
24	17
24	18
25	16
25	17
25	18
\.


--
-- Data for Name: Brand; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public."Brand" (id, name) FROM stdin;
\.


--
-- Data for Name: Category; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public."Category" (id, name) FROM stdin;
1	Carnes e derivados
2	Cereais
3	Frango
4	Frutas
5	Hortali├ºas
6	Leguminosas
7	Ovos
\.


--
-- Data for Name: Food; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public."Food" (id, name, category_id, brand_id, image_url) FROM stdin;
1	Arroz tipo 1, cozido	2	\N	arroz-tipo-1-cozido.jpg
4	Alface crespa, crua	5	\N	alface-crespa-crua.jpg
19	Asa de frango, com pele, crua	3	\N	asa-de-frango-com-pele-crua.webp
20	Asa de frango, com pele, assada	3	\N	asa-de-frango-com-pele-assada.jpg
8	Banana prata, crua	4	\N	banana-prata-crua.webp
10	Batata inglesa, frita	5	\N	batata-inglesa-frita.webp
2	Feij├úo preto, cru	6	\N	feijao-preto-cru.jpg
3	Feij├úo preto, cozido	6	\N	feijao-preto-cozido.jpg
5	F├¡gado bovino, grelhado (bife de f├¡gado)	1	\N	figado-bovino-grelhado.jpg
11	Frango inteiro, cru, com pele	3	\N	frango-inteiro-cru.webp
12	Frango inteiro, assado, com pele	3	\N	frango inteiro-assado.webp
17	Coxa de frango, com pele, crua	3	\N	coxa-de-frango-com-pele-crua.png
18	Coxa de frango, com pele, assada	3	\N	coxa-de-frango-assada.webp
21	Cora├º├úo de frango, cru	3	\N	cora├º├úo-de-frango-cru.jpg
22	Cora├º├úo de frango, grelhado	3	\N	cora├º├úo-de-frango-grelhado.jpg
23	F├¡gado de frango, cru	3	\N	figado-de-frango-cru.jpg
24	F├¡gado de frango, grelhado	3	\N	figado-de-frango-grelhado.webp
25	Fil├® de frango ├á milanesa	3	\N	file-de-frango-a-milanesa.jpg
6	Ovo de galinha, frito	7	\N	ovo-de-galinha-frito.jpg
7	Ma├º├ú Fuji, com casca, crua	4	\N	ma├º├ú-fuji-crua.webp
9	Tomate salada, cru	5	\N	tomate-salada-cru.jpg
13	Peito de frango, sem pele, cru	3	\N	Peito-De-Frango-Sem-Pele-cru.png
14	Peito de frango, sem pele, cozido	3	\N	Peito-De-Frango-Sem-Pele-cozido.png
15	Peito de frango, com pele, cru	3	\N	peito-frango-com-pele-cru.jpg
16	Peito de frango, com pele, assado	3	\N	Peito-De-Frango-com-Pele-assado.png
\.


--
-- Data for Name: Food_Nutrient; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public."Food_Nutrient" (food_id, nutrient_id, amount) FROM stdin;
1	10	2.5
1	11	28.1
1	12	0.2
1	13	1.6
1	14	1
1	15	15
1	16	3
1	17	0.3
1	18	0
2	10	21.3
2	11	58.8
2	12	1.2
2	13	21.8
2	14	0
2	15	1355
2	16	111
2	17	5.1
2	18	0
3	10	4.5
3	11	14
3	12	0.5
3	13	8.4
3	14	2
3	15	256
3	16	29
3	17	1.5
3	18	0
4	10	1.3
4	11	1.7
4	12	0.2
4	13	1.8
4	14	3
4	15	267
4	16	38
4	17	0.4
4	18	11
5	10	29.9
5	11	0
5	12	9
5	13	0
5	14	103
5	15	313
5	16	12
5	17	5.6
5	18	0
6	10	15.6
6	11	1.2
6	12	18.6
6	13	0
6	14	166
6	15	184
6	16	73
6	17	2.1
6	18	0
7	10	0.3
7	11	15.2
7	12	0
7	13	1.3
7	14	0
7	15	75
7	16	2
7	17	0.1
7	18	2.4
8	10	1.3
8	11	26
8	12	0.1
8	13	2
8	14	0
8	15	358
8	16	8
8	17	0.4
8	18	21.6
9	10	1.1
9	11	3.1
9	12	0.2
9	13	1.2
9	14	1
9	15	222
9	16	7
9	17	0.2
9	18	21.2
10	10	5
10	11	35.6
10	12	13.1
10	13	8.1
10	14	8
10	15	489
10	16	6
10	17	0.4
10	18	3.8
11	10	16.4
11	11	0
11	12	17.3
11	13	0
11	14	63
11	15	213
11	16	6
11	17	0.7
11	18	0
12	10	28
12	11	0
12	12	7.5
12	13	0
12	14	56
12	15	320
12	16	11
12	17	1.2
12	18	0
13	10	21.5
13	11	0
13	12	3
13	13	0
13	14	58
13	15	331
13	16	7
13	17	0.4
13	18	0
14	10	31.5
14	11	0
14	12	3.2
14	13	0
14	14	36
14	15	295
14	16	6
14	17	0.3
14	18	0
15	10	20.8
15	11	0
15	12	6.7
15	13	0
15	14	62
15	15	315
15	16	6
15	17	0.4
15	18	0
16	10	33.4
16	11	0
16	12	7.6
16	13	0
16	14	50
16	15	370
16	16	8
16	17	0.5
16	18	0
17	10	17.1
17	11	0
17	12	9.8
17	13	0
17	14	84
17	15	303
17	16	8
17	17	0.8
17	18	0
18	10	28.5
18	11	0
18	12	10.4
18	13	0
18	14	95
18	15	315
18	16	9
18	17	1
18	18	0
19	10	18.1
19	11	0
19	12	15.1
19	13	0
19	14	96
19	15	211
19	16	11
19	17	0.7
19	18	0
20	10	28.8
20	11	0
20	12	19
20	13	0
20	14	87
20	15	256
20	16	11
20	17	0.9
20	18	0
21	10	12.6
21	11	0.6
21	12	18.6
21	13	0
21	14	84
21	15	220
21	16	8
21	17	4.1
21	18	0
22	10	22.4
22	11	0.6
22	12	12.1
22	13	0
22	14	96
22	15	220
22	16	9
22	17	6.5
22	18	0
23	10	17.6
23	11	0
23	12	3.5
23	13	0
23	14	82
23	15	280
23	16	6
23	17	9.5
23	18	18.5
24	10	28.7
24	11	0
24	12	5.4
24	13	0
24	14	91
24	15	313
24	16	8
24	17	12.2
24	18	16.2
25	10	28.5
25	11	9.7
25	12	7.8
25	13	0.7
25	14	275
25	15	300
25	16	16
25	17	1.2
25	18	0
\.


--
-- Data for Name: Meal; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public."Meal" (id, name, calories, weight_g, consumed_at, user_id) FROM stdin;
\.


--
-- Data for Name: Meal_Food; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public."Meal_Food" (meal_id, food_id) FROM stdin;
\.


--
-- Data for Name: Nutricionist; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public."Nutricionist" (id, password, created_at, phone, email) FROM stdin;
\.


--
-- Data for Name: Nutrient; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public."Nutrient" (id, name, unit, calories_per_unit) FROM stdin;
10	Proteinas	g	4
11	Carboidratos	g	4
12	Gorduras	g	9
13	Fibras	g	0
14	Sodio	mg	0
15	Potassio	mg	0
16	Calcio	mg	0
17	Ferro	mg	0
18	Vitamina C	mg	0
\.


--
-- Data for Name: User; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public."User" (id, password, email, birthdate, weight_kg, height_m, sex, created_at, is_active, nutricionist_id) FROM stdin;
2	$argon2id$v=19$m=65536,t=3,p=4$QSBY4lwriojVs0LP6YWUNA$uIa74oi6XRml+5YAFkChRNAttCJDuVarDrQw/E4RNME	lucas@gmail.com	2007-07-07 00:00:00	89	1.75	Male	2026-08-04 15:17:24.499064	t	\N
\.


--
-- Data for Name: User_Allergen; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public."User_Allergen" (allergen_id, user_id) FROM stdin;
1	2
19	2
9	2
\.


--
-- Name: Allergen_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public."Allergen_id_seq"', 1, false);


--
-- Name: Brand_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public."Brand_id_seq"', 1, false);


--
-- Name: Category_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public."Category_id_seq"', 7, true);


--
-- Name: Food_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public."Food_id_seq"', 25, true);


--
-- Name: Meal_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public."Meal_id_seq"', 1, false);


--
-- Name: Nutricionist_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public."Nutricionist_id_seq"', 1, false);


--
-- Name: Nutrient_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public."Nutrient_id_seq"', 18, true);


--
-- Name: User_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public."User_id_seq"', 2, true);


--
-- Name: Allergen_Food Allergen_Food_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public."Allergen_Food"
    ADD CONSTRAINT "Allergen_Food_pkey" PRIMARY KEY (food_id, allergen_id);


--
-- Name: Allergen Allergen_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public."Allergen"
    ADD CONSTRAINT "Allergen_pkey" PRIMARY KEY (id);


--
-- Name: Brand Brand_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public."Brand"
    ADD CONSTRAINT "Brand_pkey" PRIMARY KEY (id);


--
-- Name: Category Category_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public."Category"
    ADD CONSTRAINT "Category_pkey" PRIMARY KEY (id);


--
-- Name: Food_Nutrient Food_Nutrient_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public."Food_Nutrient"
    ADD CONSTRAINT "Food_Nutrient_pkey" PRIMARY KEY (food_id, nutrient_id);


--
-- Name: Food Food_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public."Food"
    ADD CONSTRAINT "Food_pkey" PRIMARY KEY (id);


--
-- Name: Meal_Food Meal_Food_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public."Meal_Food"
    ADD CONSTRAINT "Meal_Food_pkey" PRIMARY KEY (meal_id, food_id);


--
-- Name: Meal Meal_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public."Meal"
    ADD CONSTRAINT "Meal_pkey" PRIMARY KEY (id);


--
-- Name: Nutricionist Nutricionist_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public."Nutricionist"
    ADD CONSTRAINT "Nutricionist_pkey" PRIMARY KEY (id);


--
-- Name: Nutrient Nutrient_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public."Nutrient"
    ADD CONSTRAINT "Nutrient_pkey" PRIMARY KEY (id);


--
-- Name: User_Allergen User_Allergen_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public."User_Allergen"
    ADD CONSTRAINT "User_Allergen_pkey" PRIMARY KEY (allergen_id, user_id);


--
-- Name: User User_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public."User"
    ADD CONSTRAINT "User_pkey" PRIMARY KEY (id);


--
-- Name: ix_Allergen_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX "ix_Allergen_id" ON public."Allergen" USING btree (id);


--
-- Name: ix_Allergen_name; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX "ix_Allergen_name" ON public."Allergen" USING btree (name);


--
-- Name: ix_Brand_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX "ix_Brand_id" ON public."Brand" USING btree (id);


--
-- Name: ix_Brand_name; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX "ix_Brand_name" ON public."Brand" USING btree (name);


--
-- Name: ix_Category_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX "ix_Category_id" ON public."Category" USING btree (id);


--
-- Name: ix_Category_name; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX "ix_Category_name" ON public."Category" USING btree (name);


--
-- Name: ix_Food_brand_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX "ix_Food_brand_id" ON public."Food" USING btree (brand_id);


--
-- Name: ix_Food_category_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX "ix_Food_category_id" ON public."Food" USING btree (category_id);


--
-- Name: ix_Food_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX "ix_Food_id" ON public."Food" USING btree (id);


--
-- Name: ix_Food_name; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX "ix_Food_name" ON public."Food" USING btree (name);


--
-- Name: ix_Meal_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX "ix_Meal_id" ON public."Meal" USING btree (id);


--
-- Name: ix_Meal_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX "ix_Meal_user_id" ON public."Meal" USING btree (user_id);


--
-- Name: ix_Nutricionist_email; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX "ix_Nutricionist_email" ON public."Nutricionist" USING btree (email);


--
-- Name: ix_Nutricionist_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX "ix_Nutricionist_id" ON public."Nutricionist" USING btree (id);


--
-- Name: ix_Nutricionist_password; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX "ix_Nutricionist_password" ON public."Nutricionist" USING btree (password);


--
-- Name: ix_Nutricionist_phone; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX "ix_Nutricionist_phone" ON public."Nutricionist" USING btree (phone);


--
-- Name: ix_Nutrient_calories_per_unit; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX "ix_Nutrient_calories_per_unit" ON public."Nutrient" USING btree (calories_per_unit);


--
-- Name: ix_Nutrient_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX "ix_Nutrient_id" ON public."Nutrient" USING btree (id);


--
-- Name: ix_Nutrient_name; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX "ix_Nutrient_name" ON public."Nutrient" USING btree (name);


--
-- Name: ix_Nutrient_unit; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX "ix_Nutrient_unit" ON public."Nutrient" USING btree (unit);


--
-- Name: ix_User_email; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX "ix_User_email" ON public."User" USING btree (email);


--
-- Name: ix_User_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX "ix_User_id" ON public."User" USING btree (id);


--
-- Name: ix_User_nutricionist_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX "ix_User_nutricionist_id" ON public."User" USING btree (nutricionist_id);


--
-- Name: Allergen_Food Allergen_Food_allergen_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public."Allergen_Food"
    ADD CONSTRAINT "Allergen_Food_allergen_id_fkey" FOREIGN KEY (allergen_id) REFERENCES public."Allergen"(id) ON DELETE CASCADE;


--
-- Name: Allergen_Food Allergen_Food_food_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public."Allergen_Food"
    ADD CONSTRAINT "Allergen_Food_food_id_fkey" FOREIGN KEY (food_id) REFERENCES public."Food"(id) ON DELETE CASCADE;


--
-- Name: Food_Nutrient Food_Nutrient_food_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public."Food_Nutrient"
    ADD CONSTRAINT "Food_Nutrient_food_id_fkey" FOREIGN KEY (food_id) REFERENCES public."Food"(id) ON DELETE CASCADE;


--
-- Name: Food_Nutrient Food_Nutrient_nutrient_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public."Food_Nutrient"
    ADD CONSTRAINT "Food_Nutrient_nutrient_id_fkey" FOREIGN KEY (nutrient_id) REFERENCES public."Nutrient"(id) ON DELETE CASCADE;


--
-- Name: Food Food_brand_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public."Food"
    ADD CONSTRAINT "Food_brand_id_fkey" FOREIGN KEY (brand_id) REFERENCES public."Brand"(id);


--
-- Name: Food Food_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public."Food"
    ADD CONSTRAINT "Food_category_id_fkey" FOREIGN KEY (category_id) REFERENCES public."Category"(id);


--
-- Name: Meal_Food Meal_Food_food_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public."Meal_Food"
    ADD CONSTRAINT "Meal_Food_food_id_fkey" FOREIGN KEY (food_id) REFERENCES public."Food"(id) ON DELETE CASCADE;


--
-- Name: Meal_Food Meal_Food_meal_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public."Meal_Food"
    ADD CONSTRAINT "Meal_Food_meal_id_fkey" FOREIGN KEY (meal_id) REFERENCES public."Meal"(id) ON DELETE CASCADE;


--
-- Name: Meal Meal_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public."Meal"
    ADD CONSTRAINT "Meal_user_id_fkey" FOREIGN KEY (user_id) REFERENCES public."User"(id);


--
-- Name: User_Allergen User_Allergen_allergen_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public."User_Allergen"
    ADD CONSTRAINT "User_Allergen_allergen_id_fkey" FOREIGN KEY (allergen_id) REFERENCES public."Allergen"(id) ON DELETE CASCADE;


--
-- Name: User_Allergen User_Allergen_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public."User_Allergen"
    ADD CONSTRAINT "User_Allergen_user_id_fkey" FOREIGN KEY (user_id) REFERENCES public."User"(id) ON DELETE CASCADE;


--
-- Name: User User_nutricionist_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public."User"
    ADD CONSTRAINT "User_nutricionist_id_fkey" FOREIGN KEY (nutricionist_id) REFERENCES public."Nutricionist"(id);


--
-- PostgreSQL database dump complete
--

\unrestrict iajnc76aAXqxIaQAJOfYCdJjPboR61uQvDBgtuPqQSYOfZMky2SqstEkNcQDIsR

