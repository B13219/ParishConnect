# ParishConnect Initial Data Model

## Core Tables

```text
branches
  id, name, location, contact_phone, created_at

users
  id, branch_id, name, email, phone, password_hash, status, created_at

roles
  id, name, description

user_roles
  user_id, role_id

members
  id, branch_id, first_name, last_name, phone, email, gender, date_of_birth,
  address, membership_status, joined_at, created_at

visitors
  id, branch_id, first_name, last_name, phone, email, visit_date,
  source, follow_up_status, converted_member_id, created_at

ministries
  id, branch_id, name, leader_member_id, created_at

ministry_members
  ministry_id, member_id, role, joined_at

events
  id, branch_id, ministry_id, name, event_type, starts_at, ends_at, location

attendance_records
  id, branch_id, event_id, person_type, member_id, visitor_id, checked_in_by,
  check_in_method, checked_in_at, corrected_at

messages
  id, branch_id, sender_user_id, channel, subject, body, audience_type,
  status, scheduled_at, sent_at, created_at

message_recipients
  id, message_id, member_id, phone, delivery_status, provider_reference

contributions
  id, branch_id, member_id, contribution_type, amount, currency,
  received_at, recorded_by, notes

imports
  id, branch_id, import_type, file_name, status, total_rows,
  successful_rows, failed_rows, created_by, created_at

audit_logs
  id, branch_id, actor_user_id, action, entity_type, entity_id,
  metadata_json, created_at
```

## Notes

- `person_type` in attendance should start with `member` and `visitor`; avoid mixing both IDs in application logic without validation.
- Financial contribution access should be limited to explicit roles.
- Branch scope should be present on operational tables for multi-branch reporting and access control.

