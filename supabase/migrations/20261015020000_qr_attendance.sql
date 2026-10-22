alter table public.pointage
  add column if not exists idempotency_key uuid;

create unique index if not exists pointage_idempotency_key_idx
  on public.pointage (idempotency_key)
  where idempotency_key is not null;

create or replace function public.rotate_personnel_qr_credential(
  target_personnel uuid,
  new_token_hash text
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if (select auth.role()) is distinct from 'service_role' then
    raise exception using
      errcode = '42501',
      message = 'Only the trusted service may issue QR credentials.';
  end if;

  if new_token_hash is null or new_token_hash !~ '^[0-9a-f]{64}$' then
    raise exception using
      errcode = '22023',
      message = 'The QR credential hash is invalid.';
  end if;

  if not exists (
    select 1
    from public.personnel as p
    join public.acces_utilisateur as a on a.id_personnel = p.id
    where p.id = target_personnel
      and p.actif
      and p.acces_approuve
      and a.role = 'personnel'::public.app_role
      and a.date_debut <= now()
      and (a.date_fin is null or a.date_fin > now())
  ) then
    raise exception using
      errcode = '42501',
      message = 'The personnel account is not eligible for a QR credential.';
  end if;

  insert into public.personnel_qr_credential (
    id_personnel,
    token_hash,
    created_at,
    revoked_at
  )
  values (target_personnel, new_token_hash, now(), null)
  on conflict (id_personnel) do update
    set token_hash = excluded.token_hash,
        created_at = excluded.created_at,
        revoked_at = null;
end;
$$;

create or replace function public.record_qr_attendance(
  target_personnel uuid,
  presented_token_hash text,
  selected_event_type public.attendance_event_type,
  request_id uuid,
  operator_user_id uuid
)
returns table (
  id_pointage uuid,
  id_personnel uuid,
  nom text,
  prenom text,
  date_heure timestamptz,
  type_pointage public.attendance_event_type,
  duplicate boolean
)
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_existing public.pointage%rowtype;
  v_inserted integer;
  v_duplicate boolean := false;
begin
  if (select auth.role()) is distinct from 'service_role' then
    raise exception using
      errcode = '42501',
      message = 'Only the trusted service may record attendance.';
  end if;

  if presented_token_hash is null
    or presented_token_hash !~ '^[0-9a-f]{64}$'
  then
    raise exception using
      errcode = '22023',
      message = 'The QR credential is invalid.';
  end if;

  if request_id is null or selected_event_type is null then
    raise exception using
      errcode = '22023',
      message = 'The attendance event is incomplete.';
  end if;

  if not exists (
    select 1
    from public.personnel as operator_person
    join public.acces_utilisateur as role_row
      on role_row.id_personnel = operator_person.id
    where operator_person.auth_user_id = operator_user_id
      and operator_person.actif
      and operator_person.acces_approuve
      and role_row.role in (
        'rh'::public.app_role,
        'scolarite'::public.app_role
      )
      and role_row.date_debut <= now()
      and (role_row.date_fin is null or role_row.date_fin > now())
  ) then
    raise exception using
      errcode = '42501',
      message = 'The operator is not authorized to record attendance.';
  end if;

  perform 1
  from public.personnel_qr_credential as credential
  join public.personnel as p on p.id = credential.id_personnel
  where credential.id_personnel = target_personnel
    and credential.token_hash = presented_token_hash
    and credential.revoked_at is null
    and p.actif
    and p.acces_approuve
    and exists (
      select 1
      from public.acces_utilisateur as role_row
      where role_row.id_personnel = p.id
        and role_row.role = 'personnel'::public.app_role
        and role_row.date_debut <= now()
        and (role_row.date_fin is null or role_row.date_fin > now())
    )
  for update of credential;

  if not found then
    raise exception using
      errcode = '22023',
      message = 'The QR credential is invalid, revoked, or inactive.';
  end if;

  select pointage.*
  into v_existing
  from public.pointage
  where pointage.idempotency_key = request_id;

  if found then
    if v_existing.id_personnel <> target_personnel
      or v_existing.type_pointage <> selected_event_type
    then
      raise exception using
        errcode = '22023',
        message = 'The idempotency key was already used for another event.';
    end if;
    v_duplicate := true;
  else

    insert into public.pointage (
      id_personnel,
      date_heure,
      type_pointage,
      mode,
      verification_reussie,
      idempotency_key
    )
    values (
      target_personnel,
      now(),
      selected_event_type,
      'qr'::public.attendance_mode,
      null,
      request_id
    )
    on conflict (idempotency_key) where idempotency_key is not null
      do nothing;

    get diagnostics v_inserted = row_count;
    if v_inserted = 0 then
      select pointage.*
      into v_existing
      from public.pointage
      where pointage.idempotency_key = request_id;

      if not found
        or v_existing.id_personnel <> target_personnel
        or v_existing.type_pointage <> selected_event_type
      then
        raise exception using
          errcode = '22023',
          message = 'The idempotency key was already used for another event.';
      end if;
      v_duplicate := true;
    else
      select pointage.*
      into v_existing
      from public.pointage
      where pointage.idempotency_key = request_id;
    end if;
  end if;

  return query
  select
    v_existing.id,
    person.id,
    person.nom,
    person.prenom,
    v_existing.date_heure,
    v_existing.type_pointage,
    v_duplicate
  from public.personnel as person
  where person.id = v_existing.id_personnel;
end;
$$;

revoke all on function public.rotate_personnel_qr_credential(uuid, text)
  from public, anon, authenticated;
grant execute on function public.rotate_personnel_qr_credential(uuid, text)
  to service_role;

revoke all on function public.record_qr_attendance(
  uuid,
  text,
  public.attendance_event_type,
  uuid,
  uuid
) from public, anon, authenticated;
grant execute on function public.record_qr_attendance(
  uuid,
  text,
  public.attendance_event_type,
  uuid,
  uuid
) to service_role;
