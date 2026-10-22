create type public.personnel_type as enum ('permanent', 'vacataire');
create type public.app_role as enum (
  'personnel',
  'rh',
  'scolarite',
  'finance',
  'admin_technique'
);
create type public.attendance_event_type as enum ('entree', 'sortie');
create type public.attendance_mode as enum ('qr', 'facial');
create type public.alert_type as enum ('absence', 'retard', 'echec_verification');
create type public.alert_status as enum ('envoyee', 'traitee');

create table public.personnel (
  id uuid primary key default gen_random_uuid(),
  auth_user_id uuid unique references auth.users (id) on delete set null,
  nom text not null,
  prenom text not null,
  email text not null unique,
  type public.personnel_type not null,
  actif boolean not null default true,
  acces_approuve boolean not null default false,
  created_at timestamptz not null default now()
);

create table public.personnel_qr_credential (
  id_personnel uuid primary key references public.personnel (id) on delete cascade,
  token_hash text not null unique,
  created_at timestamptz not null default now(),
  revoked_at timestamptz
);

create table public.acces_utilisateur (
  id uuid primary key default gen_random_uuid(),
  id_personnel uuid not null references public.personnel (id) on delete cascade,
  role public.app_role not null,
  date_debut timestamptz not null default now(),
  date_fin timestamptz,
  check (date_fin is null or date_fin > date_debut)
);

create table public.emploi_du_temps (
  id uuid primary key default gen_random_uuid(),
  id_personnel uuid not null references public.personnel (id) on delete cascade,
  debut timestamptz not null,
  fin timestamptz not null,
  type_activite text not null,
  check (fin > debut)
);

create table public.pointage (
  id uuid primary key default gen_random_uuid(),
  id_personnel uuid not null references public.personnel (id) on delete restrict,
  date_heure timestamptz not null default now(),
  type_pointage public.attendance_event_type not null,
  mode public.attendance_mode not null default 'qr',
  verification_reussie boolean,
  created_at timestamptz not null default now()
);

create table public.alerte_absence (
  id uuid primary key default gen_random_uuid(),
  id_personnel uuid not null references public.personnel (id) on delete cascade,
  id_emploi_du_temps uuid references public.emploi_du_temps (id) on delete set null,
  date_alerte timestamptz not null default now(),
  type public.alert_type not null,
  statut public.alert_status not null default 'envoyee'
);

create table public.correction_pointage (
  id uuid primary key default gen_random_uuid(),
  id_pointage uuid not null references public.pointage (id) on delete restrict,
  id_rh uuid not null references auth.users (id) on delete restrict,
  date_correction timestamptz not null default now(),
  motif text not null,
  ancienne_valeur timestamptz not null,
  nouvelle_valeur timestamptz not null
);

create table public.export_paie (
  id uuid primary key default gen_random_uuid(),
  periode_debut date not null,
  periode_fin date not null,
  date_export timestamptz not null default now(),
  id_createur uuid references auth.users (id) on delete set null,
  statut text not null default 'prepare',
  check (periode_fin >= periode_debut)
);

create table public.export_paie_ligne (
  id uuid primary key default gen_random_uuid(),
  id_export uuid not null references public.export_paie (id) on delete cascade,
  id_personnel uuid not null references public.personnel (id) on delete restrict,
  heures_validees numeric(7, 2) not null check (heures_validees >= 0),
  unique (id_export, id_personnel)
);

create index pointage_personnel_date_idx
  on public.pointage (id_personnel, date_heure desc);
create index acces_utilisateur_personnel_role_idx
  on public.acces_utilisateur (id_personnel, role, date_fin);
create index emploi_du_temps_personnel_debut_idx
  on public.emploi_du_temps (id_personnel, debut);
create index alerte_absence_date_statut_idx
  on public.alerte_absence (date_alerte desc, statut);
create index alerte_absence_personnel_date_idx
  on public.alerte_absence (id_personnel, date_alerte desc);
create index correction_pointage_pointage_date_idx
  on public.correction_pointage (id_pointage, date_correction desc);

create or replace function public.has_active_role(required_roles public.app_role[])
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.personnel as p
    join public.acces_utilisateur as a on a.id_personnel = p.id
    where p.auth_user_id = (select auth.uid())
      and p.actif
      and p.acces_approuve
      and a.role = any (required_roles)
      and a.date_debut <= now()
      and (a.date_fin is null or a.date_fin > now())
  );
$$;

revoke all on function public.has_active_role(public.app_role[]) from public;
grant execute on function public.has_active_role(public.app_role[]) to authenticated;

alter table public.personnel enable row level security;
alter table public.personnel_qr_credential enable row level security;
alter table public.acces_utilisateur enable row level security;
alter table public.emploi_du_temps enable row level security;
alter table public.pointage enable row level security;
alter table public.alerte_absence enable row level security;
alter table public.correction_pointage enable row level security;
alter table public.export_paie enable row level security;
alter table public.export_paie_ligne enable row level security;

revoke all on table
  public.personnel,
  public.personnel_qr_credential,
  public.acces_utilisateur,
  public.emploi_du_temps,
  public.pointage,
  public.alerte_absence,
  public.correction_pointage,
  public.export_paie,
  public.export_paie_ligne
from anon, authenticated;

grant select on table
  public.personnel,
  public.acces_utilisateur,
  public.emploi_du_temps,
  public.pointage,
  public.alerte_absence,
  public.correction_pointage,
  public.export_paie,
  public.export_paie_ligne
to authenticated;

grant insert, update, delete on table public.emploi_du_temps to authenticated;
grant update (statut) on table public.alerte_absence to authenticated;
grant insert on table public.correction_pointage to authenticated;

create policy "personnel_select_self_or_admin_roles"
  on public.personnel for select to authenticated
  using (
    (
      auth_user_id = (select auth.uid())
      and actif
      and acces_approuve
    )
    or public.has_active_role(array[
      'rh'::public.app_role,
      'scolarite'::public.app_role,
      'admin_technique'::public.app_role
    ])
  );

create policy "access_select_self_or_admin_roles"
  on public.acces_utilisateur for select to authenticated
  using (
    exists (
      select 1
      from public.personnel as p
      where p.id = id_personnel
        and p.auth_user_id = (select auth.uid())
        and p.actif
        and p.acces_approuve
    )
    or public.has_active_role(array[
      'rh'::public.app_role,
      'admin_technique'::public.app_role
    ])
  );

create policy "schedule_select_self_or_admin_roles"
  on public.emploi_du_temps for select to authenticated
  using (
    exists (
      select 1
      from public.personnel as p
      where p.id = id_personnel
        and p.auth_user_id = (select auth.uid())
        and p.actif
        and p.acces_approuve
    )
    or public.has_active_role(array[
      'rh'::public.app_role,
      'scolarite'::public.app_role,
      'admin_technique'::public.app_role
    ])
  );

create policy "schedule_manage_admin_roles"
  on public.emploi_du_temps for all to authenticated
  using (
    public.has_active_role(array[
      'rh'::public.app_role,
      'admin_technique'::public.app_role
    ])
  )
  with check (
    public.has_active_role(array[
      'rh'::public.app_role,
      'admin_technique'::public.app_role
    ])
  );

create policy "attendance_select_self_or_admin_roles"
  on public.pointage for select to authenticated
  using (
    exists (
      select 1
      from public.personnel as p
      where p.id = id_personnel
        and p.auth_user_id = (select auth.uid())
        and p.actif
        and p.acces_approuve
    )
    or public.has_active_role(array[
      'rh'::public.app_role,
      'scolarite'::public.app_role
    ])
  );

create policy "alert_select_owner_or_admin_roles"
  on public.alerte_absence for select to authenticated
  using (
    exists (
      select 1
      from public.personnel as p
      where p.id = id_personnel
        and p.auth_user_id = (select auth.uid())
        and p.actif
        and p.acces_approuve
    )
    or public.has_active_role(array[
      'rh'::public.app_role,
      'scolarite'::public.app_role
    ])
  );

create policy "alert_update_admin_roles"
  on public.alerte_absence for update to authenticated
  using (
    public.has_active_role(array[
      'rh'::public.app_role,
      'scolarite'::public.app_role
    ])
  )
  with check (
    public.has_active_role(array[
      'rh'::public.app_role,
      'scolarite'::public.app_role
    ])
  );

create policy "correction_select_admin_roles"
  on public.correction_pointage for select to authenticated
  using (
    public.has_active_role(array[
      'rh'::public.app_role,
      'scolarite'::public.app_role
    ])
  );

create policy "correction_insert_admin_roles"
  on public.correction_pointage for insert to authenticated
  with check (
    id_rh = (select auth.uid())
    and public.has_active_role(array[
      'rh'::public.app_role,
      'scolarite'::public.app_role
    ])
  );

create policy "payroll_export_select_admin_roles"
  on public.export_paie for select to authenticated
  using (
    public.has_active_role(array[
      'rh'::public.app_role,
      'finance'::public.app_role
    ])
  );

create policy "payroll_export_line_select_admin_roles"
  on public.export_paie_ligne for select to authenticated
  using (
    public.has_active_role(array[
      'rh'::public.app_role,
      'finance'::public.app_role
    ])
  );
