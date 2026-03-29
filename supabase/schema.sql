


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


CREATE SCHEMA IF NOT EXISTS "public";


ALTER SCHEMA "public" OWNER TO "pg_database_owner";


COMMENT ON SCHEMA "public" IS 'standard public schema';



CREATE OR REPLACE FUNCTION "public"."properties_sync_analysis_timestamps"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
  IF TG_OP = 'UPDATE' THEN
    IF NEW.restaurant_analysis IS DISTINCT FROM OLD.restaurant_analysis THEN
      NEW.restaurant_analyzed_at := CASE
        WHEN NEW.restaurant_analysis IS NULL THEN NULL
        WHEN btrim(NEW.restaurant_analysis) = '' THEN NULL
        ELSE now()
      END;
    END IF;
    IF NEW.retail_analysis IS DISTINCT FROM OLD.retail_analysis THEN
      NEW.retail_analyzed_at := CASE
        WHEN NEW.retail_analysis IS NULL THEN NULL
        WHEN btrim(NEW.retail_analysis) = '' THEN NULL
        ELSE now()
      END;
    END IF;
    IF NEW.foot_traffic_analysis IS DISTINCT FROM OLD.foot_traffic_analysis THEN
      NEW.foot_traffic_analyzed_at := CASE
        WHEN NEW.foot_traffic_analysis IS NULL THEN NULL
        WHEN btrim(NEW.foot_traffic_analysis) = '' THEN NULL
        ELSE now()
      END;
    END IF;
  ELSIF TG_OP = 'INSERT' THEN
    IF NEW.restaurant_analysis IS NOT NULL AND btrim(NEW.restaurant_analysis) <> '' THEN
      NEW.restaurant_analyzed_at := now();
    END IF;
    IF NEW.retail_analysis IS NOT NULL AND btrim(NEW.retail_analysis) <> '' THEN
      NEW.retail_analyzed_at := now();
    END IF;
    IF NEW.foot_traffic_analysis IS NOT NULL AND btrim(NEW.foot_traffic_analysis) <> '' THEN
      NEW.foot_traffic_analyzed_at := now();
    END IF;
  END IF;
  RETURN NEW;
END;
$$;


ALTER FUNCTION "public"."properties_sync_analysis_timestamps"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."set_updated_at"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;


ALTER FUNCTION "public"."set_updated_at"() OWNER TO "postgres";

SET default_tablespace = '';

SET default_table_access_method = "heap";


CREATE TABLE IF NOT EXISTS "public"."properties" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "crexi_id" "text",
    "crexi_url" "text",
    "address" "text" NOT NULL,
    "city" "text" DEFAULT 'New York'::"text" NOT NULL,
    "zip_code" "text",
    "latitude" double precision,
    "longitude" double precision,
    "square_footage" integer,
    "asking_rent_per_sqft" numeric(8,2),
    "description" "text" DEFAULT 'active'::"text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "restaurant_analysis" "text",
    "restaurant_analyzed_at" timestamp with time zone,
    "state_code" "text" DEFAULT 'NY'::"text" NOT NULL,
    "retail_analysis" "text",
    "retail_analyzed_at" timestamp with time zone,
    "foot_traffic_analysis" "text",
    "foot_traffic_analyzed_at" timestamp with time zone,
    "neighborhood_scan" "jsonb"
);


ALTER TABLE "public"."properties" OWNER TO "postgres";


COMMENT ON COLUMN "public"."properties"."restaurant_analysis" IS 'Cached restaurant-focused gap analysis (e.g. Google Places + Yelp). Fed to LLM for recommendations.';



COMMENT ON COLUMN "public"."properties"."restaurant_analyzed_at" IS 'Set automatically when restaurant_analysis changes. NULL = no analysis.';



COMMENT ON COLUMN "public"."properties"."retail_analysis" IS 'Cached retail gap analysis text.';



COMMENT ON COLUMN "public"."properties"."retail_analyzed_at" IS 'Set automatically when retail_analysis changes.';



COMMENT ON COLUMN "public"."properties"."foot_traffic_analysis" IS 'Cached foot-traffic analysis text.';



COMMENT ON COLUMN "public"."properties"."foot_traffic_analyzed_at" IS 'Set automatically when foot_traffic_analysis changes.';



COMMENT ON COLUMN "public"."properties"."neighborhood_scan" IS 'Raw structured scan data for ML pipeline. Serialized list of CategoryScan objects.';



CREATE TABLE IF NOT EXISTS "public"."recommendations" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "property_id" "uuid" NOT NULL,
    "rank" integer NOT NULL,
    "business_type" "text" NOT NULL,
    "score" integer NOT NULL,
    "reasoning" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "recommendations_score_check" CHECK ((("score" >= 1) AND ("score" <= 100)))
);


ALTER TABLE "public"."recommendations" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."properties_with_top_rec" AS
 SELECT "p"."id",
    "p"."crexi_id",
    "p"."crexi_url",
    "p"."address",
    "p"."city",
    "p"."zip_code",
    "p"."latitude",
    "p"."longitude",
    "p"."square_footage",
    "p"."asking_rent_per_sqft",
    "p"."description",
    "p"."created_at",
    "p"."updated_at",
    "p"."restaurant_analysis",
    "p"."restaurant_analyzed_at",
    "p"."state_code",
    "p"."retail_analysis",
    "p"."retail_analyzed_at",
    "p"."foot_traffic_analysis",
    "p"."foot_traffic_analyzed_at",
    "r"."business_type" AS "top_rec_business",
    "r"."score" AS "top_rec_score",
    "r"."reasoning" AS "top_rec_reasoning"
   FROM ("public"."properties" "p"
     LEFT JOIN LATERAL ( SELECT "recommendations"."business_type",
            "recommendations"."score",
            "recommendations"."reasoning"
           FROM "public"."recommendations"
          WHERE ("recommendations"."property_id" = "p"."id")
          ORDER BY "recommendations"."rank"
         LIMIT 1) "r" ON (true));


ALTER VIEW "public"."properties_with_top_rec" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."property_images" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "property_id" "uuid" NOT NULL,
    "storage_path" "text" NOT NULL,
    "display_order" integer DEFAULT 0 NOT NULL,
    "uploaded_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."property_images" OWNER TO "postgres";


ALTER TABLE ONLY "public"."properties"
    ADD CONSTRAINT "properties_crexi_id_key" UNIQUE ("crexi_id");



ALTER TABLE ONLY "public"."properties"
    ADD CONSTRAINT "properties_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."property_images"
    ADD CONSTRAINT "property_images_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."recommendations"
    ADD CONSTRAINT "recommendations_pkey" PRIMARY KEY ("id");



CREATE INDEX "idx_properties_zip" ON "public"."properties" USING "btree" ("zip_code");



CREATE INDEX "idx_property_images_property_id" ON "public"."property_images" USING "btree" ("property_id", "display_order");



CREATE INDEX "idx_recommendations_property" ON "public"."recommendations" USING "btree" ("property_id");



CREATE INDEX "idx_recommendations_score" ON "public"."recommendations" USING "btree" ("score" DESC);



CREATE OR REPLACE TRIGGER "trg_properties_analysis_timestamps" BEFORE INSERT OR UPDATE ON "public"."properties" FOR EACH ROW EXECUTE FUNCTION "public"."properties_sync_analysis_timestamps"();



CREATE OR REPLACE TRIGGER "trg_properties_updated_at" BEFORE UPDATE ON "public"."properties" FOR EACH ROW EXECUTE FUNCTION "public"."set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_recommendations_updated_at" BEFORE UPDATE ON "public"."recommendations" FOR EACH ROW EXECUTE FUNCTION "public"."set_updated_at"();



ALTER TABLE ONLY "public"."property_images"
    ADD CONSTRAINT "property_images_property_id_fkey" FOREIGN KEY ("property_id") REFERENCES "public"."properties"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."recommendations"
    ADD CONSTRAINT "recommendations_property_id_fkey" FOREIGN KEY ("property_id") REFERENCES "public"."properties"("id") ON DELETE CASCADE;



CREATE POLICY "Public read properties" ON "public"."properties" FOR SELECT USING (true);



CREATE POLICY "Public read recommendations" ON "public"."recommendations" FOR SELECT USING (true);



CREATE POLICY "Service insert properties" ON "public"."properties" FOR INSERT WITH CHECK (true);



CREATE POLICY "Service insert recommendations" ON "public"."recommendations" FOR INSERT WITH CHECK (true);



CREATE POLICY "Service update properties" ON "public"."properties" FOR UPDATE USING (true);



CREATE POLICY "Service update recommendations" ON "public"."recommendations" FOR UPDATE USING (true);



ALTER TABLE "public"."properties" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."recommendations" ENABLE ROW LEVEL SECURITY;


GRANT USAGE ON SCHEMA "public" TO "postgres";
GRANT USAGE ON SCHEMA "public" TO "anon";
GRANT USAGE ON SCHEMA "public" TO "authenticated";
GRANT USAGE ON SCHEMA "public" TO "service_role";



GRANT ALL ON FUNCTION "public"."properties_sync_analysis_timestamps"() TO "anon";
GRANT ALL ON FUNCTION "public"."properties_sync_analysis_timestamps"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."properties_sync_analysis_timestamps"() TO "service_role";



GRANT ALL ON FUNCTION "public"."set_updated_at"() TO "anon";
GRANT ALL ON FUNCTION "public"."set_updated_at"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."set_updated_at"() TO "service_role";



GRANT ALL ON TABLE "public"."properties" TO "anon";
GRANT ALL ON TABLE "public"."properties" TO "authenticated";
GRANT ALL ON TABLE "public"."properties" TO "service_role";



GRANT ALL ON TABLE "public"."recommendations" TO "anon";
GRANT ALL ON TABLE "public"."recommendations" TO "authenticated";
GRANT ALL ON TABLE "public"."recommendations" TO "service_role";



GRANT ALL ON TABLE "public"."properties_with_top_rec" TO "anon";
GRANT ALL ON TABLE "public"."properties_with_top_rec" TO "authenticated";
GRANT ALL ON TABLE "public"."properties_with_top_rec" TO "service_role";



GRANT ALL ON TABLE "public"."property_images" TO "anon";
GRANT ALL ON TABLE "public"."property_images" TO "authenticated";
GRANT ALL ON TABLE "public"."property_images" TO "service_role";



ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "service_role";







