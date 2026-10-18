"""Adds placeholder employers and open jobs so the site has content while you build.

Safe to run more than once: employers and jobs that already exist are skipped.
The seed employers get random passwords nobody knows, so they can't be logged into.
"""
import secrets
from datetime import timedelta

from app import create_app
from app.extensions import db
from app.models import User, EmployerProfile, Job, utcnow
from app.routes.jobs import get_or_create_skills

COMPANIES = [
    {"email": "hr@savannahtech.example", "name": "Savannah Tech", "location": "Nairobi",
     "website": "https://savannahtech.example",
     "description": "Software studio building web and mobile products for East African businesses."},
    {"email": "hr@riftvalleyanalytics.example", "name": "Rift Valley Analytics", "location": "Nakuru",
     "website": "https://riftvalleyanalytics.example",
     "description": "Data and AI consultancy turning raw data into decisions."},
    {"email": "hr@lakesidehealth.example", "name": "Lakeside Health Systems", "location": "Kisumu",
     "website": "https://lakesidehealth.example",
     "description": "Health-tech company digitising clinics and patient records."},
    {"email": "hr@greengridenergy.example", "name": "GreenGrid Energy", "location": "Mombasa",
     "website": "https://greengridenergy.example",
     "description": "Solar and smart-grid company serving homes and small businesses."},
    {"email": "hr@pesalabs.example", "name": "Pesa Labs", "location": "Nairobi",
     "website": "https://pesalabs.example",
     "description": "Fintech building payment and mobile money products."},
]

# (company index, title, description, location, work_mode, job_type,
#  pay_min, pay_max, currency, skills, posted_days_ago)
JOBS = [
    (0, "Backend Engineer (Python)",
     "Design and build REST APIs for client projects using Flask and PostgreSQL. You will work closely with the frontend team and ship every week.",
     "Nairobi", "hybrid", "full-time", 120000, 180000, "KES", ["Python", "Flask", "PostgreSQL"], 2),
    (0, "React Frontend Developer",
     "Build fast, accessible interfaces for web apps used by thousands of people. You will turn Figma designs into clean React code.",
     "Anywhere in Kenya", "remote", "full-time", 100000, 160000, "KES", ["JavaScript", "React", "CSS"], 4),
    (0, "QA Automation Engineer",
     "Write automated tests that catch bugs before our customers do. You will own test coverage across web and API projects.",
     "Nairobi", "hybrid", "contract", 70000, 110000, "KES", ["Testing", "Selenium", "Python"], 9),
    (0, "UI/UX Designer",
     "Design clear, modern product screens and prototypes, and test them with real users. Part-time, with room to grow into a full-time role.",
     "Anywhere in Kenya", "remote", "part-time", 50000, 80000, "KES", ["Figma", "UI Design", "Prototyping"], 6),
    (1, "Data Analyst",
     "Clean, analyse and visualise client data, then explain what it means in plain language. You will build weekly dashboards for decision makers.",
     "Nakuru", "onsite", "full-time", 90000, 140000, "KES", ["SQL", "Excel", "Power BI"], 1),
    (1, "Machine Learning Engineer",
     "Train, evaluate and deploy models that solve real business problems. You will take work from notebook to production API.",
     "Anywhere in Kenya", "remote", "full-time", 1500, 2500, "USD", ["Python", "Machine Learning", "TensorFlow"], 3),
    (1, "Data Annotation Specialist",
     "Label text and images to train AI systems, following detailed guidelines. Strong English and close attention to detail are essential.",
     "Anywhere in Kenya", "remote", "contract", 400, 700, "USD", ["Data Labeling", "Attention to Detail", "English"], 5),
    (1, "Junior Data Engineer",
     "Help build the pipelines that move data from client systems into our warehouse. A great first role for a graduate with solid SQL.",
     "Nairobi", "hybrid", "full-time", 80000, 120000, "KES", ["Python", "SQL", "ETL"], 12),
    (2, "Full-Stack Developer",
     "Build features for our clinic management platform across the Flask backend and JavaScript frontend. Your work will be used in real clinics.",
     "Kisumu", "hybrid", "full-time", 110000, 170000, "KES", ["JavaScript", "Flask", "PostgreSQL"], 7),
    (2, "Health Informatics Officer",
     "Manage clinic data quality, produce monthly reports and train staff on our systems. A health or IT background is welcome.",
     "Kisumu", "onsite", "full-time", 85000, 130000, "KES", ["Health Informatics", "SQL", "Reporting"], 10),
    (2, "Technical Writer",
     "Write user guides, API documentation and release notes that people actually read. Part-time and fully remote.",
     "Anywhere in Kenya", "remote", "part-time", 40000, 70000, "KES", ["Technical Writing", "Documentation", "English"], 15),
    (3, "IoT Embedded Engineer",
     "Write firmware for solar charge controllers and smart meters, and test it on real hardware. You will work with our field team.",
     "Mombasa", "onsite", "full-time", 100000, 150000, "KES", ["C", "Embedded Systems", "IoT"], 8),
    (3, "DevOps Engineer",
     "Run our cloud infrastructure and automate deployments. You will improve reliability, monitoring and release speed.",
     "Anywhere in Kenya", "remote", "full-time", 1800, 2800, "USD", ["Docker", "CI/CD", "Linux"], 2),
    (3, "Customer Success Associate",
     "Onboard new customers, answer questions and make sure people get value from our products. Good communication matters most.",
     "Mombasa", "hybrid", "full-time", 55000, 85000, "KES", ["Communication", "CRM", "Customer Support"], 11),
    (4, "Mobile Developer (Flutter)",
     "Build and maintain our customer-facing mobile app for Android and iOS. You will own features from idea to store release.",
     "Nairobi", "hybrid", "full-time", 110000, 170000, "KES", ["Flutter", "Dart", "REST APIs"], 4),
    (4, "Cybersecurity Analyst",
     "Monitor our systems for threats, run security reviews and respond to incidents. Payments data means security is a top priority here.",
     "Nairobi", "onsite", "full-time", 130000, 200000, "KES", ["Security", "Networking", "Incident Response"], 6),
    (4, "Payments Integration Engineer (M-Pesa)",
     "Integrate mobile money and card payments into client systems using M-Pesa APIs. Short contract with a strong chance of extension.",
     "Nairobi", "hybrid", "contract", 120000, 180000, "KES", ["M-Pesa", "Python", "APIs"], 3),
    (4, "Product Manager",
     "Decide what we build next by talking to customers, studying the data and working with engineers. You will own the roadmap for one product.",
     "Anywhere in Kenya", "remote", "full-time", 150000, 230000, "KES", ["Product Management", "Agile", "Roadmapping"], 13),
]


def get_or_create_employer(company):
    user = User.query.filter_by(email=company["email"]).first()
    if user and user.employer_profile:
        return user.employer_profile

    user = User(email=company["email"], role="employer")
    user.set_password(secrets.token_urlsafe(24))
    db.session.add(user)
    db.session.flush()

    profile = EmployerProfile(
        user_id=user.id,
        company_name=company["name"],
        website=company["website"],
        location=company["location"],
        description=company["description"],
        is_approved=True,
    )
    db.session.add(profile)
    db.session.flush()
    return profile


def main():
    app = create_app()
    with app.app_context():
        profiles = [get_or_create_employer(c) for c in COMPANIES]

        added = skipped = 0
        for (ci, title, desc, location, mode, jtype, pmin, pmax, currency, skills, days_ago) in JOBS:
            profile = profiles[ci]
            if Job.query.filter_by(employer_id=profile.id, title=title).first():
                skipped += 1
                continue

            job = Job(
                employer_id=profile.id,
                title=title,
                description=desc,
                location=location,
                work_mode=mode,
                job_type=jtype,
                pay_min=pmin,
                pay_max=pmax,
                currency=currency,
                status="open",
                created_at=utcnow() - timedelta(days=days_ago),
            )
            job.skills = get_or_create_skills(skills)
            db.session.add(job)
            added += 1

        db.session.commit()
        print(f"Jobs added: {added}, already existed: {skipped}")


if __name__ == "__main__":
    main()