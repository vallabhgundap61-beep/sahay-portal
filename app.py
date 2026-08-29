import os
import uuid
import anthropic
import cloudinary
import cloudinary.uploader
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.utils import secure_filename

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

csrf = CSRFProtect(app)
limiter = Limiter(get_remote_address, app=app, default_limits=["200 per day", "50 per hour"])

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Cloudinary SDK auto-configures from the CLOUDINARY_URL env var if present.
# Without it, uploads fall back to local disk (fine for local dev, but won't
# survive a Render redeploy — see report_issue()).
CLOUDINARY_CONFIGURED = bool(os.environ.get('CLOUDINARY_URL'))


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# Database Configuration: Uses Render's Postgres URL if available, falls back to local SQLite
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///sahay.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# Database Model for Community Issues
class Issue(db.Model):
    __tablename__ = 'issues'
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    lat = db.Column(db.Float, default=18.5204)
    lng = db.Column(db.Float, default=73.8567)
    image_url = db.Column(db.String(255), default="")
    status = db.Column(db.String(50), default="Submitted")
    upvotes = db.Column(db.Integer, default=1)


SAHAY_CATEGORIES = {
    "women-safety": {
        "title": "Women Safety",
        "description": "Immediate helplines, support networks, legal rights, and reporting channels for women.",
        "helplines": [
            {"name": "National Women Helpline", "number": "1091"},
            {"name": "National Commission for Women (NCW)", "number": "7827170170"},
            {"name": "Domestic Abuse Hotline", "number": "181"}
        ],
        "todos": [
            "Ensure you are in a safe, well-lit public space or locked room.",
            "Contact emergency services via 112 or local police instantly.",
            "Preserve any digital evidence (texts, photos, call logs) if applicable."
        ],
        "laws": "Protection of Women from Domestic Violence Act (2005), The Sexual Harassment of Women at Workplace (POSH) Act, 2013.",
        "eseva": "Nearest Women Police Station & Local District Protection Cell"
    },
    "mental-health": {
        "title": "Mental Health",
        "description": "24/7 counseling support, psychological first aid, and mental health crisis networks.",
        "helplines": [
            {"name": "Tele-MANAS Mental Health Support", "number": "14416"},
            {"name": "Vandrevala Foundation Helpline", "number": "9999 666 555"},
            {"name": "National Suicide Prevention Lifeline", "number": "9152987821"}
        ],
        "todos": [
            "Reach out immediately to a trusted friend, family member, or professional counselor.",
            "Focus on slow, deep breathing exercises to ground yourself during acute panic.",
            "Call a 24/7 crisis helpline where support is strictly confidential."
        ],
        "laws": "Mental Healthcare Act (2017) ensuring right to mental healthcare and decriminalization of suicide attempts.",
        "eseva": "District Mental Health Programme (DMHP) Clinic & Certified Community Health Centers"
    },
    "cyber-fraud": {
        "title": "Cyber Fraud",
        "description": "Reporting financial scams, identity theft, cyberstalking, and online fraud.",
        "helplines": [
            {"name": "National Cyber Crime Reporting Helpline", "number": "1930"},
            {"name": "Official Cyber Crime Portal", "number": "cybercrime.gov.in"}
        ],
        "todos": [
            "Call 1930 immediately within the 'Golden Hour' to block fraudulent financial transactions.",
            "Change online banking and email passwords instantly and log out of all active sessions.",
            "Take screenshots of transaction texts, payment gateways, and chat logs."
        ],
        "laws": "Information Technology (IT) Act, 2000 (Section 66C for identity theft and 66D for cheating by impersonation).",
        "eseva": "Cyber Crime Cell at Local District Headquarters or Authorized Common Service Centers (CSCs)"
    },
    "utilities-disruption": {
        "title": "Utilities & Disruption",
        "description": "Power outages, water supply failures, gas line leaks, and municipal service disruptions.",
        "helplines": [
            {"name": "National Electricity Emergency / Disruption", "number": "1912"},
            {"name": "Municipal Water Supply Board", "number": "1916"}
        ],
        "todos": [
            "Turn off main electrical breakers or water valves if there is risk of leakage or short circuit.",
            "Keep emergency flashlights ready and avoid touching downed power lines.",
            "Log your complaint code through utility helplines for tracking."
        ],
        "laws": "Electricity Act (2003) & Consumer Protection Rights regarding continuous essential public utility supply.",
        "eseva": "Local Electricity Board Sub-station & Municipal Ward Office"
    },
    "environment-civic": {
        "title": "Environment & Civic",
        "description": "Potholes, broken streetlights, illegal dumping, pollution, and civic maintenance requests.",
        "helplines": [
            {"name": "Municipal Corporation Helpdesk", "number": "1920"},
            {"name": "Green / Pollution Control Board", "number": "1800-11-2055"}
        ],
        "todos": [
            "Take a clear photograph of the civic hazard (pothole, garbage dump, broken light).",
            "Note down the landmark or exact street address.",
            "Submit a report on the Sahay Live Issue Feed to get community upvotes."
        ],
        "laws": "Environment (Protection) Act, 1986 & Municipal Solid Waste Management Rules.",
        "eseva": "Municipal Zonal Office & Citizen Service Bureau"
    },
    "construction": {
        "title": "Construction",
        "description": "Unsafe construction sites, building code violations, and worker welfare grievance redressal.",
        "helplines": [
            {"name": "Labour Ministry Grievance Helpline", "number": "1800-180-2126"},
            {"name": "Municipal Town Planning Cell", "number": "011-2337-1234"}
        ],
        "todos": [
            "Keep a safe distance from unstable structures or active construction hazards.",
            "Document illegal or hazardous construction practices with timestamps.",
            "File a formal ticket with the municipal town planning cell."
        ],
        "laws": "Building and Other Construction Workers (BOCW) Act & National Building Code Regulations.",
        "eseva": "Town Planning Department Office & Labour Welfare Facilitation Center"
    },
    "courier-logistics": {
        "title": "Courier & Logistics",
        "description": "Disputed shipments, cargo damage complaints, logistics delays, and postal fraud assistance.",
        "helplines": [
            {"name": "National Consumer Helpline", "number": "1915"},
            {"name": "India Post Customer Care", "number": "1800-266-6868"}
        ],
        "todos": [
            "Keep tracking numbers, waybills, and shipping receipts accessible.",
            "Record unboxing videos if you receive damaged or tampered goods.",
            "Lodge an initial grievance ticket with the courier service provider."
        ],
        "laws": "Consumer Protection Act, 2019 regarding deficiency in commercial logistics services.",
        "eseva": "District Consumer Disputes Redressal Commission & Post Office Hub"
    },
    "waste-recycling": {
        "title": "Waste & Recycling",
        "description": "Missed garbage collection, hazardous waste disposal, and neighborhood cleanliness issues.",
        "helplines": [
            {"name": "Sanitation & Swachhata Helpline", "number": "1969"},
            {"name": "Local Municipal Waste Control", "number": "311"}
        ],
        "todos": [
            "Segregate waste into dry, wet, and hazardous bins as per local protocols.",
            "Report missed garbage pickups to your local municipal ward supervisor.",
            "Avoid open burning of plastic or municipal waste."
        ],
        "laws": "Solid Waste Management Rules, 2016 under the Ministry of Environment.",
        "eseva": "Ward Sanitation Office & Authorized Dry Waste Collection Centers"
    },
    "local-community": {
        "title": "Local Community",
        "description": "Neighborhood coordination, local dispute resolution, welfare schemes, and civic assemblies.",
        "helplines": [
            {"name": "District Collectorate Helpdesk", "number": "1077"},
            {"name": "Local Police Station Control Room", "number": "112"}
        ],
        "todos": [
            "Organize community meetings through local Residents Welfare Associations (RWA).",
            "Engage local representatives for neighborhood development matters.",
            "Verify government welfare schemes available for your locality."
        ],
        "laws": "Local Municipal Governance Acts & Societies Registration Regulations.",
        "eseva": "Taluka/District Collector Office & Gram Panchayat / Ward Secretariat"
    },
    "child-protection": {
        "title": "Child Protection",
        "description": "Rescue operations, child labor reporting, missing children support, and welfare guidance.",
        "helplines": [
            {"name": "Childline India", "number": "1098"},
            {"name": "National Commission for Protection of Child Rights", "number": "011-23478200"}
        ],
        "todos": [
            "Contact Childline 1098 immediately if a child is in distress, abandoned, or exploited.",
            "Note down specific location details and descriptions.",
            "Ensure the child is moved to a secure environment if safe to do so."
        ],
        "laws": "Juvenile Justice Act (2015) and Protection of Children from Sexual Offences (POCSO) Act, 2012.",
        "eseva": "District Child Protection Unit (DCPU) & Specialized Juvenile Police Units"
    },
    "senior-citizens": {
        "title": "Senior Citizens",
        "description": "Elder abuse reporting, medical emergency assistance, and pension coordination.",
        "helplines": [
            {"name": "National Elder Helpline (Elder Line)", "number": "14567"},
            {"name": "Senior Citizen Welfare Bureau", "number": "1291"}
        ],
        "todos": [
            "Call Elder Line 14567 for rescue, emotional support, or legal guidance.",
            "Keep emergency medical contacts and prescription files easily reachable.",
            "Verify identity credentials before letting unfamiliar individuals into your home."
        ],
        "laws": "Maintenance and Welfare of Parents and Senior Citizens Act, 2007.",
        "eseva": "District Social Welfare Office & Senior Citizen Help Desks"
    },
    "legal-aid": {
        "title": "Legal Aid",
        "description": "Free legal advice, pro-bono lawyer connections, and dispute mediation assistance.",
        "helplines": [
            {"name": "National Legal Services Authority (NALSA)", "number": "15100"},
            {"name": "Supreme Court Legal Services Committee", "number": "011-23381073"}
        ],
        "todos": [
            "Gather all relevant documents, notices, agreements, or identity proofs.",
            "Contact NALSA for eligibility criteria regarding free legal representation.",
            "Consult panel advocates at district legal service clinics."
        ],
        "laws": "Legal Services Authorities Act, 1987 guaranteeing free legal aid to eligible citizens.",
        "eseva": "District Legal Services Authority (DLSA) Office at District Court Premises"
    },
    "disaster-management": {
        "title": "Disaster Management",
        "description": "Flood, earthquake, cyclone response, relief camps, and emergency rescue dispatch.",
        "helplines": [
            {"name": "National Disaster Management Authority (NDMA)", "number": "1078"},
            {"name": "State Disaster Response Force Control", "number": "112"}
        ],
        "todos": [
            "Evacuate immediately to designated high-ground relief camps or shelters.",
            "Keep an emergency kit ready with water, dry rations, and first aid.",
            "Stay tuned to official weather alerts and avoid flooded underpasses."
        ],
        "laws": "Disaster Management Act, 2005 establishing institutional mechanisms for disaster response.",
        "eseva": "District Emergency Operation Center (DEOC) & Civil Defense Offices"
    },
    "road-safety": {
        "title": "Road Safety & Transport",
        "description": "Highway accidents, reckless driving reporting, vehicle breakdowns, and transit complaints.",
        "helplines": [
            {"name": "National Highway Helpline", "number": "1033"},
            {"name": "Traffic Police Control Room", "number": "1095"}
        ],
        "todos": [
            "Move injured individuals to safety and call ambulance 108 or highway patrol 1033.",
            "Turn on hazard lights if your vehicle breaks down on high-speed corridors.",
            "Note vehicle license plates in case of reckless driving or hit-and-runs."
        ],
        "laws": "Motor Vehicles (Amendment) Act, 2019 regarding traffic offenses and road safety rules.",
        "eseva": "Regional Transport Office (RTO) & Traffic Police Headquarters"
    },
    "medical-emergency": {
        "title": "Medical Emergency",
        "description": "Ambulance dispatch, blood bank availability, poison control, and emergency hospital care.",
        "helplines": [
            {"name": "National Ambulance Service", "number": "108"},
            {"name": "AIIMS Emergency Control Room", "number": "011-26594499"}
        ],
        "todos": [
            "Dial 108 immediately for urgent ambulance and paramedic dispatch.",
            "Keep patient medical history and current medication lists ready.",
            "Administer basic first aid or CPR if trained while waiting for medical help."
        ],
        "laws": "Clinical Establishments Act & Good Samaritan Guidelines protecting bystanders helping accident victims.",
        "eseva": "Government District Hospital & Authorized Trauma Centers"
    },
    "consumer-rights": {
        "title": "Consumer Rights",
        "description": "Product fraud, unfair trade practices, overpricing, and defective services redressal.",
        "helplines": [
            {"name": "National Consumer Helpline", "number": "1915"},
            {"name": "Jago Grahak Jago Cell", "number": "1800-11-4000"}
        ],
        "todos": [
            "Preserve original purchase bills, warranty cards, and transaction receipts.",
            "Register formal complaints on the National Consumer Helpline portal.",
            "Send legal notices to merchants for major breach of warranty or defective sales."
        ],
        "laws": "Consumer Protection Act, 2019 covering misleading advertisements and product liability.",
        "eseva": "District Consumer Forum & Civil Supply Office"
    },
    "agriculture": {
        "title": "Agriculture & Farming",
        "description": "Crop insurance assistance, farmer welfare schemes, and market price grievances.",
        "helplines": [
            {"name": "Kisan Call Center", "number": "1800-180-1551"},
            {"name": "PM-KISAN Helpdesk", "number": "155261"}
        ],
        "todos": [
            "Check soil health cards and register for state-backed crop insurance packages.",
            "Contact Kisan Call Center for expert agronomic advice.",
            "Verify direct benefit transfer statuses for agricultural subsidies."
        ],
        "laws": "Agricultural Produce Market Committee (APMC) Acts & Seed Control Regulations.",
        "eseva": "Krishi Seva Kendra & District Agriculture Department Office"
    },
    "travel-tourism": {
        "title": "Travel & Tourism",
        "description": "Tourist safety support, passport help, stranded traveler assistance, and heritage complaints.",
        "helplines": [
            {"name": "Incredible India Tourist Helpline", "number": "1363"},
            {"name": "Ministry of External Affairs Support", "number": "1800-11-3090"}
        ],
        "todos": [
            "Keep digital copies of passports, visas, and hotel reservations securely backed up.",
            "Contact tourist police units or embassy helpdesks if stranded.",
            "Avoid unlicensed tour operators or unverified transit brokers."
        ],
        "laws": "Model Guidelines for Safe and Honorable Tourism & Foreigners Act.",
        "eseva": "State Tourism Information Bureau & Foreigners Regional Registration Office (FRRO)"
    },
    "tech-support": {
        "title": "Tech Support & Portals",
        "description": "Assistance with digital governance portals, Aadhaar, PAN, and government app glitches.",
        "helplines": [
            {"name": "Digital India Service Desk", "number": "1800-3000-3468"},
            {"name": "UIDAI Aadhaar Helpline", "number": "1947"}
        ],
        "todos": [
            "Clear browser caches or use official government mobile applications (Umang, DigiLocker).",
            "Verify OTP security and never share credentials over phone calls.",
            "Log portal transaction error codes for technical escalation."
        ],
        "laws": "Information Technology Act, 2000 & Digital Personal Data Protection (DPDP) Act, 2023.",
        "eseva": "Aadhaar Seva Kendra & Common Service Centers (CSC e-Governance)"
    },
    "animal-rescue": {
        "title": "Animal Welfare & Rescue",
        "description": "Injured stray animals, animal cruelty reporting, and wildlife rescue coordination.",
        "helplines": [
            {"name": "Animal Welfare Board Helpdesk", "number": "011-23383679"},
            {"name": "Local Stray Animal Ambulance", "number": "1962"}
        ],
        "todos": [
            "Keep a safe distance from injured or panic-stricken stray/wild animals.",
            "Contact local animal rescue NGOs or municipal veterinary vans with precise locations.",
            "Report cases of animal cruelty with photo/video proof to enforcement authorities."
        ],
        "laws": "Prevention of Cruelty to Animals Act, 1960 and Wildlife Protection Act, 1972.",
        "eseva": "Municipal Veterinary Hospital & Society for the Prevention of Cruelty to Animals (SPCA)"
    },
    "fire-services": {
        "title": "Fire & Rescue",
        "description": "Building fires, industrial hazards, short-circuit outbreaks, and rescue operations.",
        "helplines": [
            {"name": "National Fire Emergency Service", "number": "101"},
            {"name": "Disaster Fire Dispatch", "number": "112"}
        ],
        "todos": [
            "Evacuate the building immediately using staircases, never use elevators.",
            "Stay close to the floor if there is heavy smoke to avoid inhaling toxic fumes.",
            "Call Fire Emergency 101 or 112 as soon as you reach a safe zone."
        ],
        "laws": "National Building Code Fire Safety Standards & State Fire Force Acts.",
        "eseva": "Local Fire Station Headquarters & Municipal Disaster Cell"
    },
    "railway-safety": {
        "title": "Railway Safety",
        "description": "Train travel security, medical assistance on board, and railway property complaints.",
        "helplines": [
            {"name": "Railway Protection Force (RPF) Security", "number": "139"},
            {"name": "Indian Railways General Helpline", "number": "138"}
        ],
        "todos": [
            "Pull the alarm chain only during genuine emergencies on board trains.",
            "Contact RPF security 139 for thefts, harassment, or medical emergencies on trains.",
            "Keep luggage tagged and secure while transiting through railway platforms."
        ],
        "laws": "Railways Act, 1989 governing passenger safety and railway offenses.",
        "eseva": "Railway Station Superintendent Office & RPF Post"
    },
    "blood-bank": {
        "title": "Blood Bank & Plasma",
        "description": "Locating emergency blood groups, plasma donors, and blood donation camps.",
        "helplines": [
            {"name": "e-RaktKosh National Blood Helpline", "number": "104"},
            {"name": "Red Cross Society Blood Desk", "number": "011-23716441"}
        ],
        "todos": [
            "Check e-RaktKosh portal or call 104 for real-time blood group availability.",
            "Bring replacement donors or medical requisitions when visiting blood banks.",
            "Verify blood bank licensing and cross-matching clearances."
        ],
        "laws": "Drugs and Cosmetics Act governing blood storage banks and transfusion standards.",
        "eseva": "Government Hospital Blood Bank & Red Cross Society Center"
    },
    "general-help": {
        "title": "General Help & Queries",
        "description": "General assistance, directory inquiries, directory mappings, and portal guidance.",
        "helplines": [
            {"name": "Sahay Citizen Helpdesk", "number": "112"},
            {"name": "National Directory Information", "number": "1950"}
        ],
        "todos": [
            "Browse through specialized categories on Sahay for targeted municipal help.",
            "Use the Sahay Copilot floating chat assistant for instant guidance.",
            "Report unresolved civic issues via the community feedback feed."
        ],
        "laws": "Right to Information (RTI) Act, 2005 for transparency in public governance.",
        "eseva": "District Public Relations Office & Citizen Facilitation Center"
    }
}


# Automatically initialize database tables and seed sample issues if empty
with app.app_context():
    db.create_all()
    if Issue.query.count() == 0:
        sample_issues = [
            Issue(
                category="Environment & Civic",
                description="Large deep pothole causing traffic obstruction near central market junction.",
                lat=18.5204, lng=73.8567, image_url="", status="In Progress", upvotes=12
            ),
            Issue(
                category="Utilities & Disruption",
                description="Streetlights completely non-functional for past 3 nights on main avenue.",
                lat=18.5314, lng=73.8446, image_url="", status="Submitted", upvotes=8
            )
        ]
        db.session.add_all(sample_issues)
        db.session.commit()


@app.route('/')
def index():
    return render_template('index.html', categories=SAHAY_CATEGORIES)


@app.route('/category/<category_id>')
def view_category(category_id):
    category_data = SAHAY_CATEGORIES.get(category_id)
    if not category_data:
        return render_template('index.html', categories=SAHAY_CATEGORIES), 404
    return render_template('category_detail.html', category=category_data, category_id=category_id)


@app.route('/issues-feed')
def issues_feed():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    pagination = Issue.query.order_by(Issue.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return render_template('issues_feed.html', issues=pagination.items, pagination=pagination)


@app.route('/report', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=["POST"])
def report_issue():
    if request.method == 'POST':
        category = request.form.get('category', 'General Help').strip()
        description = request.form.get('description', '').strip()

        if not category or not description:
            return render_template('report.html', error="Category and description are required.", categories=SAHAY_CATEGORIES), 400

        try:
            lat = float(request.form.get('lat', 18.5204))
            lng = float(request.form.get('lng', 73.8567))
        except ValueError:
            lat, lng = 18.5204, 73.8567

        image_url = ""
        file = request.files.get('image')
        if file and file.filename != '':
            if not allowed_file(file.filename):
                return render_template('report.html', error="Unsupported file type. Please upload a PNG, JPG, GIF, or WEBP image.", categories=SAHAY_CATEGORIES), 400

            if CLOUDINARY_CONFIGURED:
                try:
                    upload_result = cloudinary.uploader.upload(file, folder="sahay_issues", resource_type="image")
                    image_url = upload_result.get('secure_url', '')
                except Exception as e:
                    app.logger.error(f"Cloudinary upload failed: {e}")
                    return render_template('report.html', error="Image upload failed. Please try again.", categories=SAHAY_CATEGORIES), 500
            else:
                filename = secure_filename(file.filename)
                unique_name = f"{uuid.uuid4().hex}_{filename}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
                file.save(filepath)
                image_url = f"/static/uploads/{unique_name}"

        new_issue = Issue(
            category=category,
            description=description,
            lat=lat,
            lng=lng,
            image_url=image_url,
            status="Submitted",
            upvotes=1
        )
        db.session.add(new_issue)
        db.session.commit()
        return redirect(url_for('issues_feed'))

    return render_template('report.html', categories=SAHAY_CATEGORIES)


@app.route('/upvote/<int:issue_id>', methods=['POST'])
@limiter.limit("20 per minute")
def upvote_issue(issue_id):
    issue = Issue.query.get(issue_id)
    if issue:
        issue.upvotes += 1
        db.session.commit()
    return redirect(url_for('issues_feed'))


@app.route('/healthz')
def healthz():
    return {"status": "ok"}, 200


@app.route('/api/copilot', methods=['POST'])
@csrf.exempt
@limiter.limit("10 per minute")
def copilot_chat():
    data = request.get_json(silent=True) or {}
    user_message = (data.get('message') or '').strip()

    if not user_message:
        return {"error": "Message is required."}, 400
    if len(user_message) > 500:
        return {"error": "Message is too long (max 500 characters)."}, 400

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        return {"reply": "The Copilot isn't fully set up yet — the site owner needs to add an ANTHROPIC_API_KEY. In the meantime, browse the category list above for verified helplines."}

    # Ground the assistant in Sahay's own helpline data so it doesn't hallucinate numbers
    context_lines = []
    for cat in SAHAY_CATEGORIES.values():
        helplines = ", ".join(f"{h['name']}: {h['number']}" for h in cat['helplines'])
        context_lines.append(f"- {cat['title']}: {helplines}")
    context = "\n".join(context_lines)

    system_prompt = (
        "You are Sahay Copilot, a helpful assistant embedded in the Sahay citizen support portal (India). "
        "Answer briefly, in 2-4 sentences. When relevant, point the user to the specific helpline number from "
        "this verified list rather than a number you recall from elsewhere:\n\n"
        f"{context}\n\n"
        "If the user describes a genuine emergency in progress, always tell them to call 112 (India's national "
        "emergency number) immediately, in addition to any category-specific helpline. "
        "You are not a substitute for professional legal, medical, or psychological advice, and should say so "
        "if the question calls for that kind of professional care."
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=300,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}]
        )
        reply_text = "".join(block.text for block in response.content if block.type == "text")
        return {"reply": reply_text or "I'm not sure how to help with that — try rephrasing, or browse the category list above."}
    except Exception as e:
        app.logger.error(f"Copilot error: {e}")
        return {"reply": "Sorry, I'm having trouble responding right now. For emergencies, please call 112 directly."}


@app.route('/robots.txt')
def robots_txt():
    body = f"User-agent: *\nAllow: /\nSitemap: {request.url_root.rstrip('/')}/sitemap.xml\n"
    return app.response_class(body, mimetype='text/plain')


@app.route('/sitemap.xml')
def sitemap_xml():
    base_url = request.url_root.rstrip('/')
    pages = ['/', '/issues-feed', '/report'] + [f'/category/{cat_id}' for cat_id in SAHAY_CATEGORIES]
    xml_parts = ['<?xml version="1.0" encoding="UTF-8"?>',
                 '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for p in pages:
        xml_parts.append(f'<url><loc>{base_url}{p}</loc></url>')
    xml_parts.append('</urlset>')
    return app.response_class("\n".join(xml_parts), mimetype='application/xml')


# Global Error Handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('error.html', error_code=404, error_message="The requested resource or page could not be found."), 404


@app.errorhandler(429)
def rate_limit_error(error):
    return render_template('error.html', error_code=429, error_message="You're doing that a bit too fast. Please wait a moment and try again."), 429


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('error.html', error_code=500, error_message="An internal server error occurred while processing your request."), 500


if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true', port=5000)
