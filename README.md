# APAAR-Based Student Data Management and Verification System

A responsive, standalone frontend prototype for demonstrating an AICTE-style student data integrity portal.

## Open in VS Code
1. Extract `APAAR_Student_Verification_System.zip`.
2. Open the extracted folder in Visual Studio Code.
3. Open `index.html` in a browser, or use the **Live Server** extension and click **Go Live**.
4. On the sign-in page, choose a demo role:
   - AICTE Administrator
   - Institution Administrator
   - Verifier

No Node.js, database, API key, or installation is required for this frontend demo.

## Features
- Role-select demo login
- Dashboard KPIs, sample verification trend and data-quality visualisation
- Student directory with search and status filters
- Add/edit student records with basic field validation
- CSV import for sample student records
- Validation queue and mark-reviewed actions
- Potential duplicate-enrolment review workflow
- Institution directory with approved-intake vs admission monitoring
- Simulated student verification lookup
- CSV exports for student, institution and validation summaries
- Responsive layout for desktop and mobile

## Important limitations
- All records and APAAR identifiers are fictional sample data.
- Verification is simulated locally; this is not connected to APAAR, AICTE, DigiLocker, Aadhaar, or any government registry.
- The login is a demo role switch, not real authentication. Role restrictions are not server-enforced.
- Data changes live only in the current browser session and reset on refresh.
- Do not enter real student personal information.
- A production deployment needs a backend, secure authentication, server-side role-based access control, database, audit logging, encryption, upload scanning, privacy/legal review, and authorized official API access.

## CSV import format
The importer accepts a CSV with columns such as:
`name,apaar id,institution,course,year,email,dob`
Use fictional sample records only. APAAR ID format in the demo is `APAAR-1234-5678`.
