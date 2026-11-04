# IGEO Alumni Registration & Ticketing Portal

Independent Flask application. It does not connect to the existing IGEO Fest application.

## Local setup (Windows CMD)
1. Activate your virtual environment.
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and update the values.
4. Add the official payment QR image as `static/images/payment_qr.png` (optional).
5. Run: `python app.py`
6. Open: http://127.0.0.1:5000

## Admin
Open `/admin/login`. Credentials are read from `ADMIN_USERNAME` and `ADMIN_PASSWORD` in `.env`.
Change the default credentials before use.

## Render deployment
Push this project to a private GitHub repository and deploy using the included `render.yaml` Blueprint. Set `ADMIN_PASSWORD`, `ACCOUNT_TITLE`, `BANK_NAME`, and `ACCOUNT_NUMBER` in Render environment variables. Add the payment QR image to `static/images/payment_qr.png` before deployment.

The Blueprint provisions PostgreSQL and a persistent disk for uploaded payment receipts. Do not deploy with the default development secret or default admin password.

## Important
- This starter stores receipt files on the configured upload disk. Keep the Render persistent disk attached.
- Payment screenshots are evidence only. Admin must independently verify funds received before approving.
- Ticket QR opens a verification page. It does not yet perform one-time event check-in; a check-in module can be added as the next phase.
- Email delivery is not configured in this initial version. Alumni can retrieve approved tickets through the application reference + email status page.
- Before collecting real personal/payment data, configure HTTPS, strong admin credentials, backups, privacy notice and retention policy.
