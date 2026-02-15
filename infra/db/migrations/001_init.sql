create extension if not exists pgcrypto;
create extension if not exists vector;

create table users (
  id uuid primary key default gen_random_uuid(),
  full_name text,
  email text unique,
  password_hash text,
  role text not null default ''farmer'',
  is_active boolean not null default true,
  locale text not null default ''ru'',
  created_at timestamptz not null default now()
);

create table chat_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id),
  locale text not null default ''ru'',
  created_at timestamptz not null default now()
);

create table chat_messages (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references chat_sessions(id) on delete cascade,
  role text not null check (role in (''user'',''assistant'',''system'',''tool'')),
  content text not null,
  tool_name text,
  safety_level text,
  trace_id uuid,
  created_at timestamptz not null default now()
);

create table documents (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid references users(id),
  title text not null,
  language text default ''ru'',
  status text not null default ''processing'',
  storage_path text not null,
  metadata jsonb not null default ''{}''::jsonb,
  created_at timestamptz not null default now()
);

create table document_chunks (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references documents(id) on delete cascade,
  chunk_text text not null,
  embedding vector(768) not null,
  token_count int,
  chunk_index int not null,
  metadata jsonb not null default ''{}''::jsonb
);

create index if not exists document_chunks_embedding_cos_idx
  on document_chunks using ivfflat (embedding vector_cosine_ops) with (lists = 100);

create index if not exists document_chunks_fts_idx
  on document_chunks using gin (to_tsvector(''simple'', chunk_text));

create table tool_calls (
  id uuid primary key default gen_random_uuid(),
  session_id uuid references chat_sessions(id) on delete set null,
  message_id uuid references chat_messages(id) on delete set null,
  tool_name text not null,
  input jsonb not null,
  output jsonb,
  status text not null,
  latency_ms int,
  created_at timestamptz not null default now()
);

create table eval_datasets (
  id uuid primary key default gen_random_uuid(),
  name text unique not null,
  version text not null,
  language text not null default ''ru'',
  created_at timestamptz not null default now()
);

create table eval_items (
  id uuid primary key default gen_random_uuid(),
  dataset_id uuid not null references eval_datasets(id) on delete cascade,
  question text not null,
  expected_policy jsonb not null default ''{}''::jsonb,
  expected_facts jsonb not null default ''{}''::jsonb
);

create table eval_runs (
  id uuid primary key default gen_random_uuid(),
  dataset text not null,
  model text not null,
  status text not null default ''queued'',
  metrics jsonb not null default ''{}''::jsonb,
  sample_size int not null default 50,
  created_at timestamptz not null default now()
);

create table jobs (
  id uuid primary key default gen_random_uuid(),
  job_type text not null,
  status text not null default ''queued'',
  payload jsonb not null default ''{}''::jsonb,
  result jsonb not null default ''{}''::jsonb,
  error text,
  created_at timestamptz not null default now()
);

create table agent_steps (
  id uuid primary key default gen_random_uuid(),
  trace_id uuid not null,
  parent_step_id uuid,
  agent_name text not null,
  step_type text not null,
  parent_hash text,
  step_hash text not null,
  payload jsonb not null default ''{}''::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists ix_agent_steps_trace_id on agent_steps(trace_id);
