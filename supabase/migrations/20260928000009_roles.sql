-- Application roles. Roles are cluster-level and survive `db reset`, so creation is idempotent.
-- LOGIN is granted here so `db diff` stays clean; passwords are set per environment by
-- infra/scripts/setup_roles.sh, never here. A login role without a password cannot authenticate.
do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'gravv_api') then
    create role gravv_api nologin;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'gravv_worker') then
    create role gravv_worker nologin;
  end if;
end $$;
alter role gravv_api with login;
alter role gravv_worker with login;
grant authenticated to gravv_api;
grant anon to gravv_api;
grant service_role to gravv_worker;
