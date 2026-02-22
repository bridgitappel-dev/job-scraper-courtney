import requests
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import os 

print("="*60)
print("JOB SCRAPER FOR COURTNEY - WILLOW GROVE, PA")
print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*60)

all_jobs = []

# ADZUNA - Search near Willow Grove, PA (19090)
print("\nSearching Adzuna near Willow Grove, PA...")
app_id = os.getenv('ADZUNA_APP_ID')
app_key = os.getenv('ADZUNA_APP_KEY')

if app_id and app_key:
    searches = [
        "product manager",
        "technical product manager",
        "senior product manager",
        "digital product manager"
    ]
    
    for query in searches:
        print(f"\n  Query: {query}")
        for page in range(1, 3):
            try:
                url = f"https://api.adzuna.com/v1/api/jobs/us/search/{page}"
                params = {
                    "app_id": app_id,
                    "app_key": app_key,
                    "what": query,
                    "where": "Willow Grove, PA",
                    "distance": 40,
                    "results_per_page": 50,
                    "max_days_old": 30,
                    "sort_by": "date"
                }
                
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()
                
                jobs = response.json().get("results", [])
                if not jobs:
                    break
                
                for job in jobs:
                    location = job.get("location", {})
                    salary_min = job.get("salary_min")
                    salary_max = job.get("salary_max")
                    salary = None
                    
                    if salary_min and salary_max:
                        salary = f"${int(salary_min):,} - ${int(salary_max):,}"
                    
                    all_jobs.append({
                        "title": job.get("title", ""),
                        "company": job.get("company", {}).get("display_name", "Unknown"),
                        "location": location.get("display_name", "Not specified"),
                        "salary": salary,
                        "url": job.get("redirect_url", ""),
                        "description": job.get("description", "")[:300],
                        "source": "Adzuna"
                    })
                
                print(f"    Page {page}: Found {len(jobs)} jobs")
            except Exception as e:
                print(f"    Error: {e}")
                break
else:
    print("  Adzuna credentials not found")

# THE MUSE - Remote jobs only
print("\nSearching The Muse (Remote only)...")
base_url = "https://www.themuse.com/api/public/jobs"
searches = [
    {"category": "Product Management", "level": "Mid Level", "location": "Remote"},
    {"category": "Product Management", "level": "Senior Level", "location": "Remote"},
]

for search in searches:
    print(f"\n  Query: {search}")
    for page in range(2):
        try:
            params = {**search, "page": page, "descending": True}
            response = requests.get(base_url, params=params, timeout=10)
            response.raise_for_status()
            
            jobs = response.json().get("results", [])
            if not jobs:
                break
                
            for job in jobs:
                company = job.get("company", {})
                locations = job.get("locations", [])
                location_str = ", ".join([loc.get("name", "") for loc in locations])
                
                all_jobs.append({
                    "title": job.get("name", ""),
                    "company": company.get("name", "Unknown"),
                    "location": location_str or "Remote",
                    "salary": None,
                    "url": job.get("refs", {}).get("landing_page", ""),
                    "description": job.get("contents", "")[:300],
                    "source": "The Muse"
                })
            
            print(f"    Page {page}: Found {len(jobs)} jobs")
        except Exception as e:
            print(f"    Error: {e}")
            break

print(f"\nTotal jobs found: {len(all_jobs)}")

# Remove duplicates
unique = {}
for job in all_jobs:
    key = f"{job['title']}_{job['company']}".lower()
    if key not in unique:
        unique[key] = job

filtered = list(unique.values())
print(f"After deduplication: {len(filtered)} jobs")

# Save to file
with open("daily_jobs.json", "w") as f:
    json.dump(filtered, f, indent=2)
print("Saved to daily_jobs.json")

# Send email
if filtered:
    print("\nSending email...")
    
    smtp_server = os.getenv('SMTP_SERVER')
    smtp_port = int(os.getenv('SMTP_PORT', '587'))
    sender = os.getenv('SENDER_EMAIL')
    password = os.getenv('SENDER_PASSWORD')
    recipients = os.getenv('RECIPIENT_EMAIL', '').split(',')
    
    subject = f"Daily Job Alert - {len(filtered)} Product Manager Jobs (Willow Grove + Remote)"
    
    html = f"""<html><body style="font-family: Arial, sans-serif;">
    <div style="background-color: #667eea; color: white; padding: 20px; text-align: center;">
        <h1>Daily Job Matches</h1>
        <p>{datetime.now().strftime('%B %d, %Y')}</p>
    </div>
    
    <div style="padding: 20px;">
        <h2>{len(filtered)} Product Manager Jobs Found</h2>
        <p>Near Willow Grove, PA (40 miles) + Remote opportunities</p>
    """
    
    for i, job in enumerate(filtered[:15], 1):
        salary_line = f"<p><strong>Salary:</strong> {job['salary']}</p>" if job.get('salary') else ""
        
        html += f"""
        <div style="border:1px solid #ddd; padding:15px; margin:15px 0; border-radius:5px;">
            <h3 style="color: #667eea;">{i}. {job['title']}</h3>
            <p><strong>{job['company']}</strong></p>
            <p>📍 {job['location']}</p>
            {salary_line}
            <p style="font-size:12px; color:#888;">Source: {job['source']}</p>
            <a href="{job['url']}" style="background-color:#667eea; color:white; padding:10px 20px; text-decoration:none; border-radius:5px; display:inline-block; margin-top:10px;">View Job</a>
        </div>
        """
    
    if len(filtered) > 15:
        html += f"<p style='text-align:center;'><em>Plus {len(filtered)-15} more jobs...</em></p>"
    
    html += "</div></body></html>"
    
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = ', '.join(recipients)
    msg.attach(MIMEText(html, 'html'))
    
    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender, password)
            server.send_message(msg)
        print(f"Email sent to: {', '.join(recipients)}")
    except Exception as e:
        print(f"Email error: {e}")
else:
    print("\nNo jobs found")

print("\nDone!")
