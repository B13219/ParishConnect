# ParishConnect Product Requirements

## Problem

Churches often manage members, visitors, attendance, offerings, events, and communications using paper registers, spreadsheets, and informal message chains. This creates duplicated data, weak follow-up, slow reporting, and poor visibility for leaders.

## Users

| Role | Primary Needs |
| --- | --- |
| Administrator | Manage users, settings, branches, reports, and system access. |
| Pastor / Leader | View reports, send messages, manage ministries, and follow up with members. |
| Receptionist | Register visitors, update member records, and check attendance. |
| Usher | Mark attendance quickly before, during, or after service. |
| Member | View profile, events, messages, and contribution history. |
| Guest / Visitor | Register, receive follow-up, and become a member when ready. |

## MVP Features

### Registration

- Create visitor records.
- Create member records.
- Convert visitor to member.
- Capture contact details, branch, ministry, and household information.
- Import initial data from Excel or CSV.

### Attendance

- Check in by QR code.
- Check in manually by usher or receptionist.
- Track attendance by service, event, branch, and date.
- Allow authorized post-service corrections.

### Communication

- Send announcements to all members, groups, branches, or ministries.
- Support push notifications, SMS, and in-app messages.
- Store message delivery status where providers support callbacks.

### Events And Ministries

- Create services, events, and ministry meetings.
- Assign members to ministries.
- Track event attendance.

### Stewardship

- Record tithe and offering entries.
- Send reminders.
- Provide member contribution history.
- Produce financial reports for authorized roles.

### Reporting

- Attendance trend reports.
- Visitor follow-up reports.
- Member engagement reports.
- Contribution summaries.
- Data export for administrators.

## Non-Functional Requirements

- Role-based access control.
- Audit trail for sensitive changes.
- Encrypted transport using HTTPS.
- Secure password storage.
- Daily database backups.
- Offline-friendly attendance capture for unreliable internet environments.
- Simple interface for non-technical church staff.

## Out Of Scope For First MVP

- Full accounting system.
- Anonymous giving.
- Advanced AI insights.
- Payroll or HR management.
- Public website builder.

## Later Phase: Member App / Webapp

After SMS and USSD access is solid, ParishConnect should add a richer member self-service app or webapp. This should work like a banking app in principle: members can view their own records and initiate simple requests, while church staff retain approval authority for sensitive changes.

Target member capabilities:

- View profile, household, ministry, and branch details.
- View giving history, receipts, and weekly/monthly contribution summaries.
- Receive announcements, reminders, and event notices.
- Check in through QR attendance when available.
- Join church livestreams from verified YouTube or meeting links.
- Submit prayer, pastoral follow-up, or profile update requests.
- Request transfer to another church branch or record a church move.
- Access approved digital giving once payment providers are integrated.

This should follow SMS/USSD because feature-phone access will be more inclusive during the transition away from paper registers.

## Long-Term Platform Vision: Church Network App

The member app can later grow beyond one church's private self-service portal into a wider church network experience. This would let members follow verified church news, services, events, and livestreams across participating churches while still keeping each church's private records protected.

Potential network capabilities:

- National church news feed with posts from verified churches, dioceses, ministries, or branches.
- Followed-church stream so members can see updates only from churches and ministries they care about.
- Online attendance for YouTube livestreams, Zoom meetings, conferences, and remote services.
- Event discovery for crusades, conferences, road seminars, youth events, charity drives, and ministry trainings.
- Road seminar pages with location, route/city, dates, speaker/ministry, livestream link, and attendance capture.
- Sermon, teaching, and devotional media library.
- Prayer requests and testimony posts with moderation controls.
- Cross-branch transfer requests where the receiving church can approve and onboard the member.
- Push/SMS reminders for followed events and online services.

This should be treated as a later platform layer, not the first product promise. The first product must win trust by solving church administration, attendance, stewardship, reports, SMS/USSD, and payment workflows well.
