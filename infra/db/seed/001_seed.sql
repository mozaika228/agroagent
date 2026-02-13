begin;

-- Demo admin user (no password hash by design; use /v1/auth/register for real auth setup).
insert into users (id, full_name, email, role, is_active, locale)
select
  '00000000-0000-0000-0000-000000000001',
  'AgroAgent Admin',
  'admin@agroagent.local',
  'admin',
  true,
  'ru'
where not exists (
  select 1 from users where id = '00000000-0000-0000-0000-000000000001'
);

-- Demo dataset metadata for evaluation workflows.
insert into eval_datasets (id, name, version, language)
select
  '10000000-0000-0000-0000-000000000001',
  'zko_farmers_v1',
  '1.0.0',
  'ru'
where not exists (
  select 1 from eval_datasets where id = '10000000-0000-0000-0000-000000000001'
);

commit;
