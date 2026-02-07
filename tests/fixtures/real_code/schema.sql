--
-- PostgreSQL database dump
--

SET client_encoding = 'UTF8';
SET standard_conforming_strings = off;
SET check_function_bodies = false;
SET client_min_messages = warning;
SET escape_string_warning = off;

--
-- Name: SCHEMA public; Type: COMMENT; Schema: -; Owner: postgres
--

COMMENT ON SCHEMA public IS 'Standard public schema';


--
-- Name: plpgsql; Type: PROCEDURAL LANGUAGE; Schema: -; Owner: postgres
--

CREATE OR REPLACE PROCEDURAL LANGUAGE plpgsql;


ALTER PROCEDURAL LANGUAGE plpgsql OWNER TO postgres;

SET search_path = public, pg_catalog;

--
-- Name: actor_actor_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE actor_actor_id_seq
    INCREMENT BY 1
    NO MAXVALUE
    NO MINVALUE
    CACHE 1;


ALTER TABLE public.actor_actor_id_seq OWNER TO postgres;

SET default_tablespace = '';

SET default_with_oids = false;

--
-- Name: actor; Type: TABLE; Schema: public; Owner: postgres; Tablespace: 
--

CREATE TABLE actor (
    actor_id integer DEFAULT nextval('actor_actor_id_seq'::regclass) NOT NULL,
    first_name character varying(45) NOT NULL,
    last_name character varying(45) NOT NULL,
    last_update timestamp without time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.actor OWNER TO postgres;

--
-- Name: mpaa_rating; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE mpaa_rating AS ENUM (
    'G',
    'PG',
    'PG-13',
    'R',
    'NC-17'
);


ALTER TYPE public.mpaa_rating OWNER TO postgres;

--
-- Name: year; Type: DOMAIN; Schema: public; Owner: postgres
--

CREATE DOMAIN year AS integer
	CONSTRAINT year_check CHECK (((VALUE >= 1901) AND (VALUE <= 2155)));


ALTER DOMAIN public.year OWNER TO postgres;

--
-- Name: _group_concat(text, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION _group_concat(text, text) RETURNS text
    AS $_$
SELECT CASE
  WHEN $2 IS NULL THEN $1
  WHEN $1 IS NULL THEN $2
  ELSE $1 || ', ' || $2
END
$_$
    LANGUAGE sql IMMUTABLE;


ALTER FUNCTION public._group_concat(text, text) OWNER TO postgres;
