# ParishConnect API Outline

## Authentication

- `POST /auth/login`
- `POST /auth/logout`
- `POST /auth/password-reset/request`
- `POST /auth/password-reset/confirm`

## Members And Visitors

- `GET /members`
- `POST /members`
- `GET /members/{member_id}`
- `PATCH /members/{member_id}`
- `GET /visitors`
- `POST /visitors`
- `POST /visitors/{visitor_id}/convert`

## Attendance

- `GET /events`
- `POST /events`
- `POST /attendance/check-in`
- `POST /attendance/manual`
- `PATCH /attendance/{attendance_id}`
- `GET /reports/attendance`

## Messaging

- `GET /messages`
- `POST /messages`
- `GET /messages/{message_id}/recipients`
- `POST /webhooks/sms-delivery`
- `POST /webhooks/push-delivery`

## Stewardship

- `GET /contributions`
- `POST /contributions`
- `GET /members/{member_id}/contributions`
- `GET /reports/contributions`

## Import

- `POST /imports/members`
- `POST /imports/visitors`
- `GET /imports/{import_id}`

## Admin

- `GET /users`
- `POST /users`
- `PATCH /users/{user_id}`
- `GET /roles`
- `POST /users/{user_id}/roles`

