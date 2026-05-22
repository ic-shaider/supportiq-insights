"""Generate realistic mock support ticket data modeled on IC support patterns."""

import random
from datetime import datetime, timedelta
from app.models.database import (
    init_db, SessionLocal, SupportTicket, ResolutionPattern,
    TicketCategory, TicketSeverity, TicketStatus, AffectedSystem, Base, engine
)

TICKET_TEMPLATES = [
    # Payment Processing
    {"title": "ACH payment failing for {biller} policyholders", "desc": "Multiple ACH payments returning with code R01 (Insufficient Funds) for {biller}. Payers report sufficient balance. Possible processor issue.", "cat": TicketCategory.PAYMENT_PROCESSING, "sys": AffectedSystem.PAYMENT_SERVICE, "sev": TicketSeverity.HIGH},
    {"title": "Credit card transactions timing out", "desc": "Credit card payment processing taking >30 seconds for {biller}. Chase screening API returning intermittent timeouts. Some transactions failing.", "cat": TicketCategory.PAYMENT_PROCESSING, "sys": AffectedSystem.PAYMENT_SERVICE, "sev": TicketSeverity.HIGH},
    {"title": "Duplicate payment charges for {biller}", "desc": "Several policyholders of {biller} reporting duplicate charges on their credit card statement. Need to investigate and refund.", "cat": TicketCategory.PAYMENT_PROCESSING, "sys": AffectedSystem.PAYMENT_SERVICE, "sev": TicketSeverity.CRITICAL},
    {"title": "Payment reconciliation mismatch", "desc": "Daily reconciliation for {biller} shows $12,450 discrepancy between processed payments and settlement file. Need investigation.", "cat": TicketCategory.PAYMENT_PROCESSING, "sys": AffectedSystem.PAYMENT_SERVICE, "sev": TicketSeverity.HIGH},
    {"title": "Guest pay not working for {biller}", "desc": "Payers unable to complete guest payments on {biller} portal. Getting 'Invalid policy number' error even with valid policy numbers.", "cat": TicketCategory.PAYMENT_PROCESSING, "sys": AffectedSystem.NBE_PORTAL, "sev": TicketSeverity.MEDIUM},
    # Biller Configuration
    {"title": "Need to enable AutoPay for {biller}", "desc": "{biller} requesting AutoPay enrollment feature be enabled for their policyholders. Currently disabled in biller config.", "cat": TicketCategory.BILLER_CONFIGURATION, "sys": AffectedSystem.BILLER_CONFIG, "sev": TicketSeverity.LOW},
    {"title": "Billing cycle change for {biller}", "desc": "{biller} wants to change from quarterly to monthly billing for their homeowners LOB. Need config update.", "cat": TicketCategory.BILLER_CONFIGURATION, "sys": AffectedSystem.BILLER_CONFIG, "sev": TicketSeverity.LOW},
    {"title": "Notification template update for {biller}", "desc": "{biller} wants to update their payment due email template with new branding and contact information.", "cat": TicketCategory.BILLER_CONFIGURATION, "sys": AffectedSystem.NOTIFICATION, "sev": TicketSeverity.LOW},
    {"title": "Feature flag enable: pay-by-text for {biller}", "desc": "Enable pay-by-text feature flag for {biller}. They completed SMS opt-in compliance review.", "cat": TicketCategory.BILLER_CONFIGURATION, "sys": AffectedSystem.BILLER_CONFIG, "sev": TicketSeverity.LOW},
    # Integration
    {"title": "Guidewire sync failing for {biller}", "desc": "Guidewire BillingCenter sync for {biller} returning 500 errors since yesterday. Policy data not updating. Webhook receiving but failing to process.", "cat": TicketCategory.INTEGRATION, "sys": AffectedSystem.GUIDEWIRE, "sev": TicketSeverity.CRITICAL},
    {"title": "API endpoint returning 504 for {biller}", "desc": "{biller}'s payment API calls getting 504 Gateway Timeout. Their system reports connection established but no response. Intermittent - happens about 30% of calls.", "cat": TicketCategory.INTEGRATION, "sys": AffectedSystem.API_GATEWAY, "sev": TicketSeverity.HIGH},
    {"title": "Webhook delivery failures", "desc": "Payment confirmation webhooks not being delivered to {biller}'s endpoint. Queue is growing. 500+ undelivered in last 6 hours.", "cat": TicketCategory.INTEGRATION, "sys": AffectedSystem.API_GATEWAY, "sev": TicketSeverity.HIGH},
    {"title": "OAuth token refresh failing", "desc": "{biller}'s OAuth refresh token expired. API calls returning 401. Need to regenerate client credentials.", "cat": TicketCategory.INTEGRATION, "sys": AffectedSystem.AUTH, "sev": TicketSeverity.MEDIUM},
    # User Access
    {"title": "Agent unable to log into portal", "desc": "Insurance agent for {biller} cannot log into the biller portal. Getting 'Account locked' message after password reset.", "cat": TicketCategory.USER_ACCESS, "sys": AffectedSystem.AUTH, "sev": TicketSeverity.LOW},
    {"title": "SSO not working after domain change", "desc": "{biller} recently changed their email domain. SSO logins failing for all users with new domain. Need SAML config update.", "cat": TicketCategory.USER_ACCESS, "sys": AffectedSystem.AUTH, "sev": TicketSeverity.MEDIUM},
    {"title": "Permission denied on reporting dashboard", "desc": "Manager at {biller} cannot access reporting dashboard. Seeing 403 error. Should have admin role.", "cat": TicketCategory.USER_ACCESS, "sys": AffectedSystem.REPORTING, "sev": TicketSeverity.LOW},
    # Performance
    {"title": "Portal loading very slowly for {biller}", "desc": "Biller portal for {biller} taking 15+ seconds to load dashboard. Users complaining. All other billers seem fine.", "cat": TicketCategory.PERFORMANCE, "sys": AffectedSystem.NBE_PORTAL, "sev": TicketSeverity.MEDIUM},
    {"title": "Reporting queries timing out", "desc": "Daily payment report for {biller} timing out. Query runs for 10+ minutes. Dataset has grown significantly.", "cat": TicketCategory.PERFORMANCE, "sys": AffectedSystem.DATABASE, "sev": TicketSeverity.MEDIUM},
    {"title": "High API response latency", "desc": "API response times for {biller} averaging 5s (normally <500ms). No obvious load spike. Database queries look normal.", "cat": TicketCategory.PERFORMANCE, "sys": AffectedSystem.API_GATEWAY, "sev": TicketSeverity.HIGH},
    # Data Issues
    {"title": "Missing policy data after sync", "desc": "200+ policies for {biller} not appearing in IC after latest Guidewire sync. Policies exist in Guidewire but not in our system.", "cat": TicketCategory.DATA_ISSUES, "sys": AffectedSystem.GUIDEWIRE, "sev": TicketSeverity.HIGH},
    {"title": "Reporting dashboard showing wrong numbers", "desc": "{biller} reports that payment totals on dashboard don't match their bank settlement. Off by ~$8,200.", "cat": TicketCategory.DATA_ISSUES, "sys": AffectedSystem.REPORTING, "sev": TicketSeverity.MEDIUM},
    {"title": "Duplicate policyholder records", "desc": "Found 50+ duplicate policyholder records for {biller} after migration. Causing confusion in payment matching.", "cat": TicketCategory.DATA_ISSUES, "sys": AffectedSystem.DATABASE, "sev": TicketSeverity.MEDIUM},
]

BILLERS = [
    "Texas Farm Bureau Insurance", "DB Insurance", "FCCI Insurance Group",
    "Texas Mutual Insurance", "Safety Insurance", "Norfolk & Dedham",
    "CDE Lightband", "Soquel Creek Water", "JCSA", "City of Wylie",
    "FrankCrum Insurance", "Flagstaff Water", "Metro Utilities",
]

RESOLUTION_PATTERNS = [
    ResolutionPattern(pattern_name="ACH R01 Processor Retry", category=TicketCategory.PAYMENT_PROCESSING, affected_system=AffectedSystem.PAYMENT_SERVICE, trigger_keywords=["ach", "r01", "insufficient", "processor", "failing"], resolution_steps="1. Check processor connection status in PaymentProcessingService\n2. Verify ACH batch file format matches processor specs\n3. Retry failed transactions with exponential backoff\n4. If persistent, contact Chase/processor support with transaction IDs", resolution_type="workaround", auto_resolvable=False, success_rate=0.75, times_used=45),
    ResolutionPattern(pattern_name="Enable AutoPay Feature Flag", category=TicketCategory.BILLER_CONFIGURATION, affected_system=AffectedSystem.BILLER_CONFIG, trigger_keywords=["enable", "autopay", "auto pay", "feature", "config"], resolution_steps="1. Navigate to BillerConfigurationService\n2. Set feature_flag.autopay_enabled = true for biller\n3. Verify payment method ACH is enabled\n4. Confirm recurring payment schedule is configured", resolution_type="config_change", auto_resolvable=True, auto_resolve_script="UPDATE biller_config SET autopay_enabled=TRUE WHERE biller_id=:biller_id", success_rate=0.95, times_used=120),
    ResolutionPattern(pattern_name="Billing Cycle Update", category=TicketCategory.BILLER_CONFIGURATION, affected_system=AffectedSystem.BILLER_CONFIG, trigger_keywords=["billing cycle", "change", "monthly", "quarterly", "frequency"], resolution_steps="1. Update billing_cycle in BillerConfigurationService\n2. Set new billing frequency\n3. Update notification templates for new schedule\n4. Notify affected policyholders", resolution_type="config_change", auto_resolvable=True, auto_resolve_script="UPDATE billing_config SET frequency=:new_freq WHERE biller_id=:biller_id AND lob=:lob", success_rate=0.90, times_used=80),
    ResolutionPattern(pattern_name="Notification Template Update", category=TicketCategory.BILLER_CONFIGURATION, affected_system=AffectedSystem.NOTIFICATION, trigger_keywords=["notification", "template", "email", "update", "branding"], resolution_steps="1. Access notification template manager\n2. Update template content with new branding\n3. Preview and test with sample data\n4. Deploy to production", resolution_type="config_change", auto_resolvable=True, success_rate=0.92, times_used=65),
    ResolutionPattern(pattern_name="Feature Flag Toggle", category=TicketCategory.BILLER_CONFIGURATION, affected_system=AffectedSystem.BILLER_CONFIG, trigger_keywords=["feature flag", "enable", "disable", "toggle", "pay-by-text"], resolution_steps="1. Check feature flag current state\n2. Toggle feature flag via Azure App Config\n3. Verify change propagated\n4. Confirm feature is active in biller portal", resolution_type="config_change", auto_resolvable=True, success_rate=0.98, times_used=200),
    ResolutionPattern(pattern_name="Guidewire Sync Recovery", category=TicketCategory.INTEGRATION, affected_system=AffectedSystem.GUIDEWIRE, trigger_keywords=["guidewire", "sync", "failing", "500", "webhook"], resolution_steps="1. Check GuidewireCloudNativeBillingCenter logs for error details\n2. Verify Guidewire API credentials are valid\n3. Check if schema version changed (Las Leñas upgrade?)\n4. Manually trigger sync retry\n5. If schema change, update mapping in integration config", resolution_type="workaround", auto_resolvable=False, success_rate=0.60, times_used=25),
    ResolutionPattern(pattern_name="OAuth Token Refresh", category=TicketCategory.INTEGRATION, affected_system=AffectedSystem.AUTH, trigger_keywords=["oauth", "token", "refresh", "expired", "401", "credential"], resolution_steps="1. Regenerate client credentials in auth service\n2. Update stored refresh token\n3. Test API call with new credentials\n4. Monitor for 24 hours", resolution_type="config_change", auto_resolvable=True, auto_resolve_script="ROTATE client_credentials WHERE client_id=:biller_client_id", success_rate=0.88, times_used=55),
    ResolutionPattern(pattern_name="Account Unlock", category=TicketCategory.USER_ACCESS, affected_system=AffectedSystem.AUTH, trigger_keywords=["locked", "login", "unable", "access", "account"], resolution_steps="1. Verify user identity\n2. Unlock account in auth service\n3. Send password reset link\n4. Confirm user can log in", resolution_type="config_change", auto_resolvable=True, auto_resolve_script="UPDATE user_accounts SET locked=FALSE WHERE email=:user_email", success_rate=0.95, times_used=150),
    ResolutionPattern(pattern_name="SSO SAML Config Update", category=TicketCategory.USER_ACCESS, affected_system=AffectedSystem.AUTH, trigger_keywords=["sso", "saml", "domain", "idp", "federation"], resolution_steps="1. Get new IDP metadata from biller\n2. Update SAML configuration\n3. Test SSO flow with new domain\n4. Notify biller team", resolution_type="config_change", auto_resolvable=False, success_rate=0.80, times_used=15),
    ResolutionPattern(pattern_name="Permission Grant", category=TicketCategory.USER_ACCESS, affected_system=AffectedSystem.AUTH, trigger_keywords=["permission", "role", "403", "denied", "admin", "access"], resolution_steps="1. Verify requested permissions are appropriate\n2. Grant role in auth service\n3. Confirm user can access resource", resolution_type="config_change", auto_resolvable=True, auto_resolve_script="GRANT role=:role TO user_id=:user_id", success_rate=0.97, times_used=90),
    ResolutionPattern(pattern_name="Database Query Optimization", category=TicketCategory.PERFORMANCE, affected_system=AffectedSystem.DATABASE, trigger_keywords=["slow", "timeout", "query", "report", "database", "latency"], resolution_steps="1. Identify slow query in monitoring\n2. Check for missing indexes\n3. Add composite index if needed\n4. Consider query optimization or pagination\n5. Monitor performance improvement", resolution_type="workaround", auto_resolvable=False, success_rate=0.70, times_used=30),
    ResolutionPattern(pattern_name="Guest Pay Policy Validation Fix", category=TicketCategory.PAYMENT_PROCESSING, affected_system=AffectedSystem.NBE_PORTAL, trigger_keywords=["guest pay", "invalid policy", "policy number", "not working"], resolution_steps="1. Check policy number format in biller config\n2. Verify policy lookup service is responding\n3. Check if policies are synced from source system\n4. Test with known valid policy number", resolution_type="workaround", auto_resolvable=False, success_rate=0.65, times_used=20),
]


def generate_seed_data(num_tickets: int = 200):
    print("Initializing SupportIQ Insights database...")
    Base.metadata.drop_all(bind=engine)
    init_db()
    db = SessionLocal()

    try:
        # Load resolution patterns
        for pattern in RESOLUTION_PATTERNS:
            db.add(pattern)
        db.commit()
        print(f"  Loaded {len(RESOLUTION_PATTERNS)} resolution patterns")

        # Generate tickets
        now = datetime.utcnow()
        for i in range(num_tickets):
            template = random.choice(TICKET_TEMPLATES)
            biller = random.choice(BILLERS)
            age_hours = random.uniform(0.5, 720)  # 30 min to 30 days old
            created = now - timedelta(hours=age_hours)

            # Some tickets are already resolved
            status = random.choices(
                [TicketStatus.NEW, TicketStatus.TRIAGED, TicketStatus.IN_PROGRESS,
                 TicketStatus.ESCALATED, TicketStatus.RESOLVED, TicketStatus.CLOSED],
                weights=[30, 20, 15, 10, 15, 10],
            )[0]

            ticket = SupportTicket(
                ticket_id=f"SUP-{10000 + i}",
                title=template["title"].format(biller=biller),
                description=template["desc"].format(biller=biller),
                reporter_email=f"support.{random.choice(['agent', 'admin', 'user'])}@{biller.lower().replace(' ', '')}.com",
                reporter_name=random.choice(["Sarah W.", "Mike T.", "Jennifer L.", "David K.", "Amanda R.", "Chris P."]),
                biller_name=biller,
                status=status,
                created_at=created,
            )

            if status in (TicketStatus.RESOLVED, TicketStatus.CLOSED):
                ticket.resolved_at = created + timedelta(hours=random.uniform(0.5, 48))
                ticket.time_to_resolution_hours = round(
                    (ticket.resolved_at - ticket.created_at).total_seconds() / 3600, 2
                )
                ticket.resolution_type = random.choice(["manual", "auto_resolved", "escalated"])
                ticket.resolved_by = random.choice(["Support Agent", "SupportIQ AutoResolver", "Engineering"])

            db.add(ticket)

        db.commit()
        print(f"  Generated {num_tickets} support tickets")
        print(f"  Billers: {len(BILLERS)}")

    finally:
        db.close()


if __name__ == "__main__":
    generate_seed_data()
