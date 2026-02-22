import requests
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import os

print("="*60)
print("JOB SCRAPER FOR COURTNEY")
print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*60)

# Scrape The Muse
base_url = "https://www.themuse.com/api/public/jobs"
all_jobs = []

searches = [
    {"category": "Product Management", "level": "Mid Level"},
    {"category": "Product Management", "level": "Senior Level"},
]

for search in searches:
    print(f"\nSearching: {search}")
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
                    "location": location_str or "Not specified",
                    "url": job.get("refs", {}).get("landing_page", ""),
                    "description": job.get("contents", "")[:300]
                })
            
            print(f"  Page {page}: Found {len(jobs)} jobs")
        except Exception as e:
            print(f"  Error: {e}")
            break

print(f"\nTotal jobs found: {len(all_jobs)}")

# Filter for keywords
filtered = []
for job in all_jobs:
    text = f"{job['title']} {job['description']}".lower()
    if any(kw in text for kw in ["product manager", "product management", "pm"]):
        if not any(bad in text for bad in ["junior", "intern", "entry level"]):
            filtered.append(job)

print(f"After filtering: {len(filtered)} jobs")

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
    
    subject = f"Daily Job Alert - {len(filtered)} Product Manager Jobs"
    
    html = f"""<html><body>
    <h2>Daily Job Matches - {datetime.now().strftime('%B %d, %Y')}</h2>
    <p><strong>{len(filtered)} jobs found</strong></p>
    """
    
    for i, job in enumerate(filtered[:10], 1):
        html += f"""
        <div style="border:1px solid #ddd; padding:15px; margin:10px 0;">
            <h3>{i}. {job['title']}</h3>
            <p><strong>{job['company']}</strong></p>
            <p>{job['location']}</p>
            <a href="{job['url']}">View Job</a>
        </div>
        """
    
    html += "</body></html>"
    
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

print("\nDone!")
