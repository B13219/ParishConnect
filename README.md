## Current status

ParishConnect has progressed beyond the initial presentation MVP into active post-demo development. The current build provides a working administrative platform with tested backend workflows and an increasingly integrated church operations model.

Current capabilities include:

- Member and visitor registration, profiles, search, filtering, and status management
- Visitor follow-up workflows and conversion from visitor to member
- Household creation, primary contacts, dependants, and household-linked records
- Configurable local community terminology for different church structures
- Community group creation, leadership, membership, and member-profile integration
- Ministry creation, editing, leadership, membership, and member-profile integration
- Automatic ministry leader membership and leadership handover handling
- Events and service scheduling
- Ministry-linked events and meetings
- Manual, QR-code, and geofence-supported attendance workflows
- Attendance opening and closing controls
- Ministry event attendance and activity history
- Stewardship records for individual and household contributions
- Announcements and messaging workflows
- Administrative branch configuration
- Role-based permissions for administrators, pastors/leaders, receptionists, and ushers
- Audit-oriented backend workflows
- Automated API regression testing

The platform remains in active development. Production authentication hardening, hosted messaging integrations, member-facing mobile functionality, deployment infrastructure, and additional reporting capabilities remain planned work.

## Post-demo progress

Development after the first ParishConnect demonstration has focused on turning the original MVP into a more complete church operations platform.

Major additions include:

### Communities

Churches can organise members into local communities or similar structures. Administrators can configure the terminology used by their church, while community records support leaders, membership, meeting information, and integration with member profiles.

### Ministries

Ministries now support creation, editing, leaders, membership management, and member-profile visibility. Ministry leadership is permission-controlled, and assigning a leader automatically maintains the appropriate ministry membership. Leadership handovers also demote the previous leader's ministry role correctly.

### Events and attendance

Events can be associated directly with ministries. Ministry meetings therefore use ParishConnect's existing attendance engine rather than maintaining a separate attendance system.

This supports:

- Ministry-linked event creation and editing
- Ministry selection from the event interface
- Changing or removing an event's ministry association
- QR and manual attendance against ministry events
- Existing geofence attendance capabilities
- Attendance counts for ministry events
- Upcoming ministry meetings
- Historical ministry activity and attendance visibility

This creates an integrated flow:

`Ministry → Event → Attendance → Ministry activity history`

### Reliability

Backend regression coverage has expanded alongside the new functionality. Ministry membership, leadership changes, event integration, attendance behaviour, permissions, and related API workflows are covered by automated tests.

## What it does

- Manages visitors, members, households, communities, and ministries.
- Supports visitor follow-up and conversion into member records.
- Organises ministry and community membership and leadership.
- Schedules church services, events, and ministry meetings.
- Supports manual, QR-code, and geofence-assisted attendance.
- Links ministry events directly to attendance and activity history.
- Tracks individual and household stewardship records.
- Provides announcements, administrative configuration, and leadership reporting workflows.
- Uses role-based access controls to protect church information.

## Verification

- Backend automated test suite passing
- Python route compilation checks passing
- Ruff checks passing
- Alembic migrations maintained for schema changes
- Active development roadmap maintained in `docs/post-demo-roadmap.md`