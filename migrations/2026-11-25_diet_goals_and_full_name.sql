-- ---------------------------------------------------------------------------
-- Migration 2026-11-25: metas da dieta e nome completo
--
-- A API aplica este UP automaticamente no startup (shared/database.py:
-- ensure_diet_schema e ensure_full_name_schema), de forma idempotente.
-- Este arquivo documenta a mudanca e permite aplicar/reverter manualmente.
-- Nada e apagado: a coluna legada "Diet".goal e mantida com seus dados.
-- ---------------------------------------------------------------------------

-- ============================== UP =========================================
BEGIN;

-- Bancos criados pelo smart-balance.sql nao tem as metas (causa do HTTP 500
-- em POST /create_diet: UndefinedColumn kcal_goal)
ALTER TABLE "Diet" ADD COLUMN IF NOT EXISTS kcal_goal    DOUBLE PRECISION;
ALTER TABLE "Diet" ADD COLUMN IF NOT EXISTS fat_goal     DOUBLE PRECISION;
ALTER TABLE "Diet" ADD COLUMN IF NOT EXISTS carb_goal    DOUBLE PRECISION;
ALTER TABLE "Diet" ADD COLUMN IF NOT EXISTS protein_goal DOUBLE PRECISION;

-- Coluna legada (somente se existir): o model nao a preenche mais
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'Diet' AND column_name = 'goal') THEN
        ALTER TABLE "Diet" ALTER COLUMN goal DROP NOT NULL;
    END IF;
END $$;

-- Nome completo (registros existentes ficam NULL: nao ha campo de origem)
ALTER TABLE "User"         ADD COLUMN IF NOT EXISTS full_name VARCHAR;
ALTER TABLE "Nutricionist" ADD COLUMN IF NOT EXISTS full_name VARCHAR;

COMMIT;

-- ============================== DOWN =======================================
-- ATENCAO: o DOWN apaga os valores de full_name e das metas informados depois
-- do UP. Faca backup (scripts/backup-db.sh) antes. Nao e executado
-- automaticamente. Remover full_name e seguro para o codigo anterior; remover
-- as metas NAO e: o codigo anterior a esta migration ja as esperava.
--
-- BEGIN;
-- ALTER TABLE "User"         DROP COLUMN IF EXISTS full_name;
-- ALTER TABLE "Nutricionist" DROP COLUMN IF EXISTS full_name;
-- -- Metas: so remova se o banco veio do dump (tinha goal). Para voltar a
-- -- exigir goal, preencha os NULL antes:
-- -- UPDATE "Diet" SET goal = '' WHERE goal IS NULL;
-- -- ALTER TABLE "Diet" ALTER COLUMN goal SET NOT NULL;
-- -- ALTER TABLE "Diet" DROP COLUMN IF EXISTS kcal_goal, DROP COLUMN IF EXISTS fat_goal,
-- --                    DROP COLUMN IF EXISTS carb_goal, DROP COLUMN IF EXISTS protein_goal;
-- COMMIT;
