"""
Multi-Job Board Scraper Agent
Searches top 10 job boards from Willow Grove, PA 19090 (40 mile radius)
Outputs: Email with Title + Company combinations
"""

import os
import json
import sqlite3
import requests
from datetime import datetime, timedelta
from typing import List, Dict
import hashlib
import time


class MultiJobBoardAgent:
    def __init__(self, db_path: str = "jobs.db"):
        self.db_path = db_path
        
        # API Keys from environment
        self.jsearch_api_key = os.getenv("JSEARCH_API_KEY")
        self.serp_api_key = os.getenv("SERP_API_KEY")  # For Google Jobs
        self.adzuna_app_id = os.getenv("ADZUNA_APP_ID")
        self.adzuna_app_key = os.getenv("ADZUNA_APP_KEY")
        
        # Location settings for Willow Grove, PA
        self.location = "Willow Grove, PA 19090"
        self.radius_miles = 40
        self.radius_km = int(self.radius_miles * 1.60934)  # Convert to km
        
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                title TEXT,
                company TEXT,
                location TEXT,
                salary TEXT,
                job_type TEXT,
                posted_date TEXT,
                url TEXT,
                source TEXT,
                description TEXT,
                scraped_at TEXT,
                search_query TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scrape_runs (
                run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_date TEXT,
                jobs_found INTEGER,
                new_jobs INTEGER,
                queries_processed INTEGER,
                sources_scraped TEXT
            )
        """)
        
        conn.commit()
        conn.close()
    
    def _generate_job_id(self, job: Dict, source: str) -> str:
        """Generate unique ID for job"""
        unique_string = f"{job.get('title', '')}{job.get('company', '')}{source}"
        return hashlib.md5(unique_string.encode()).hexdigest()
    
    def is_duplicate(self, job_id: str) -> bool:
        """Check if job already exists"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM jobs WHERE job_id = ?", (job_id,))
        exists = cursor.fetchone() is not None
        conn.close()
        return exists
    
    # ============ JOB BOARD 1-3: JSearch API (Indeed, LinkedIn, Glassdoor aggregated) ============
    def scrape_jsearch(self, job_title: str) -> List[Dict]:
        """JSearch aggregates Indeed, LinkedIn, Glassdoor, ZipRecruiter"""
        if not self.jsearch_api_key:
            print("⚠️  JSearch API key not found")
            return []
        
        headers = {
            "X-RapidAPI-Key": self.jsearch_api_key,
            "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
        }
        
        params = {
            "query": f"{job_title} in {self.location}",
            "page": "1",
            "num_pages": "3",
            "date_posted": "today",
            "radius": str(self.radius_km)
        }
        
        try:
            response = requests.get(
                "https://jsearch.p.rapidapi.com/search",
                headers=headers,
                params=params,
                timeout=15
            )
            response.raise_for_status()
            data = response.json()
            
            jobs = []
            for item in data.get("data", []):
                jobs.append({
                    "title": item.get("job_title"),
                    "company": item.get("employer_name"),
                    "location": f"{item.get('job_city', '')}, {item.get('job_state', '')}",
                    "salary": item.get("job_salary") or "Not specified",
                    "url": item.get("job_apply_link"),
                    "posted": item.get("job_posted_at_datetime_utc"),
                    "source": "Indeed/LinkedIn/Glassdoor (JSearch)"
                })
            
            print(f"  ✓ JSearch: {len(jobs)} jobs")
            return jobs
        
        except Exception as e:
            print(f"  ✗ JSearch error: {e}")
            return []
    
    # ============ JOB BOARD 4: Adzuna API ============
    def scrape_adzuna(self, job_title: str) -> List[Dict]:
        """Adzuna job search"""
        if not self.adzuna_app_id or not self.adzuna_app_key:
            print("⚠️  Adzuna API keys not found")
            return []
        
        params = {
            "app_id": self.adzuna_app_id,
            "app_key": self.adzuna_app_key,
            "what": job_title,
            "where": self.location,
            "distance": self.radius_miles,
            "max_days_old": 1,
            "results_per_page": 50
        }
        
        try:
            response = requests.get(
                "https://api.adzuna.com/v1/api/jobs/us/search/1",
                params=params,
                timeout=15
            )
            response.raise_for_status()
            data = response.json()
            
            jobs = []
            for item in data.get("results", []):
                jobs.append({
                    "title": item.get("title"),
                    "company": item.get("company", {}).get("display_name", "Unknown"),
                    "location": item.get("location", {}).get("display_name", ""),
                    "salary": f"${item.get('salary_min', 0):,.0f} - ${item.get('salary_max', 0):,.0f}" if item.get('salary_min') else "Not specified",
                    "url": item.get("redirect_url"),
                    "posted": item.get("created"),
                    "source": "Adzuna"
                })
            
            print(f"  ✓ Adzuna: {len(jobs)} jobs")
            return jobs
        
        except Exception as e:
            print(f"  ✗ Adzuna error: {e}")
            return []
    
    # ============ JOB BOARD 5: Google Jobs via SerpAPI ============
    def scrape_google_jobs(self, job_title: str) -> List[Dict]:
        """Google Jobs via SerpAPI"""
        if not self.serp_api_key:
            print("⚠️  SerpAPI key not found")
            return []
        
        params = {
            "engine": "google_jobs",
            "q": job_title,
            "location": self.location,
            "hl": "en",
            "api_key": self.serp_api_key,
            "chips": "date_posted:today"
        }
        
        try:
            response = requests.get(
                "https://serpapi.com/search",
                params=params,
                timeout=15
            )
            response.raise_for_status()
            data = response.json()
            
            jobs = []
            for item in data.get("jobs_results", []):
                jobs.append({
                    "title": item.get("title"),
                    "company": item.get("company_name"),
                    "location": item.get("location"),
                    "salary": item.get("detected_extensions", {}).get("salary", "Not specified"),
                    "url": item.get("share_link") or item.get("related_links", [{}])[0].get("link", ""),
                    "posted": item.get("detected_extensions", {}).get("posted_at"),
                    "source": "Google Jobs"
                })
            
            print(f"  ✓ Google Jobs: {len(jobs)} jobs")
            return jobs
        
        except Exception as e:
            print(f"  ✗ Google Jobs error: {e}")
            return []
    
    # ============ JOB BOARDS 6-10: Additional free APIs ============
    def scrape_usa_jobs(self, job_title: str) -> List[Dict]:
        """USAJobs.gov API (government jobs)"""
        headers = {
            "Host": "data.usajobs.gov",
            "User-Agent": os.getenv("USAJOBS_EMAIL", "your-email@example.com")
        }
        
        params = {
            "Keyword": job_title,
            "LocationName": self.location,
            "Radius": self.radius_miles,
            "PostingChannel": "1"
        }
        
        try:
            response = requests.get(
                "https://data.usajobs.gov/api/search",
                headers=headers,
                params=params,
                timeout=15
            )
            response.raise_for_status()
            data = response.json()
            
            jobs = []
            for item in data.get("SearchResult", {}).get("SearchResultItems", []):
                matched_job = item.get("MatchedObjectDescriptor", {})
                jobs.append({
                    "title": matched_job.get("PositionTitle"),
                    "company": matched_job.get("OrganizationName"),
                    "location": matched_job.get("PositionLocationDisplay"),
                    "salary": matched_job.get("PositionRemuneration", [{}])[0].get("Description", "Not specified"),
                    "url": matched_job.get("ApplyURI", [""])[0],
                    "posted": matched_job.get("PublicationStartDate"),
                    "source": "USAJobs.gov"
                })
            
            print(f"  ✓ USAJobs: {len(jobs)} jobs")
            return jobs
        
        except Exception as e:
            print(f"  ✗ USAJobs error: {e}")
            return []
    
    def scrape_remotive(self, job_title: str) -> List[Dict]:
        """Remotive.io API (remote jobs)"""
        try:
            response = requests.get(
                "https://remotive.com/api/remote-jobs",
                timeout=15
            )
            response.raise_for_status()
            data = response.json()
            
            jobs = []
            for item in data.get("jobs", [])[:50]:  # Limit results
                if job_title.lower() in item.get("title", "").lower():
                    jobs.append({
                        "title": item.get("title"),
                        "company": item.get("company_name"),
                        "location": "Remote",
                        "salary": item.get("salary", "Not specified"),
                        "url": item.get("url"),
                        "posted": item.get("publication_date"),
                        "source": "Remotive"
                    })
            
            print(f"  ✓ Remotive: {len(jobs)} jobs")
            return jobs
        
        except Exception as e:
            print(f"  ✗ Remotive error: {e}")
            return []
    
    def save_job(self, job: Dict, search_query: str):
        """Save job to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        job_id = self._generate_job_id(job, job.get("source", "unknown"))
        
        cursor.execute("""
            INSERT OR IGNORE INTO jobs 
            (job_id, title, company, location, salary, job_type, posted_date, url, source, description, scraped_at, search_query)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job_id,
            job.get("title"),
            job.get("company"),
            job.get("location"),
            job.get("salary"),
            job.get("job_type", ""),
            job.get("posted"),
            job.get("url"),
            job.get("source"),
            "",
            datetime.now().isoformat(),
            search_query
        ))
        
        conn.commit()
        conn.close()
        
        return job_id
    
    def run_daily_scrape(self, job_titles: List[str]) -> Dict:
        """
        Run daily scrape across all job boards
        """
        print(f"\n{'='*60}")
        print(f"🚀 JOB SCRAPER AGENT - DAILY RUN")
        print(f"{'='*60}")
        print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📍 Location: {self.location}")
        print(f"📏 Radius: {self.radius_miles} miles ({self.radius_km} km)")
        print(f"🔍 Job Titles: {len(job_titles)}")
        print(f"{'='*60}\n")
        
        all_new_jobs = []
        total_jobs_found = 0
        sources_used = set()
        
        for title in job_titles:
            print(f"\n🔎 Searching: '{title}'")
            print("-" * 50)
            
            # Aggregate jobs from all sources
            all_jobs = []
            
            # Top 10 Job Boards
            all_jobs.extend(self.scrape_jsearch(title))  # 1-3: Indeed, LinkedIn, Glassdoor
            time.sleep(1)
            
            all_jobs.extend(self.scrape_adzuna(title))   # 4: Adzuna
            time.sleep(1)
            
            all_jobs.extend(self.scrape_google_jobs(title))  # 5: Google Jobs
            time.sleep(1)
            
            all_jobs.extend(self.scrape_usa_jobs(title))     # 6: USAJobs
            time.sleep(1)
            
            all_jobs.extend(self.scrape_remotive(title))     # 7: Remotive
            
            # Note: Boards 8-10 would require additional API integrations
            # Examples: CareerBuilder, Monster, Dice (require paid APIs or scraping)
            
            total_jobs_found += len(all_jobs)
            
            # Check for duplicates and save new jobs
            for job in all_jobs:
                job_id = self._generate_job_id(job, job.get("source", "unknown"))
                sources_used.add(job.get("source", "unknown"))
                
                if not self.is_duplicate(job_id):
                    self.save_job(job, title)
                    all_new_jobs.append(job)
            
            print(f"  📊 Total found: {len(all_jobs)}")
        
        print(f"\n{'='*60}")
        print(f"✅ SCRAPE COMPLETE")
        print(f"{'='*60}")
        print(f"📊 Total jobs found: {total_jobs_found}")
        print(f"🆕 New jobs: {len(all_new_jobs)}")
        print(f"🌐 Sources used: {len(sources_used)}")
        print(f"{'='*60}\n")
        
        # Save run statistics
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO scrape_runs (run_date, jobs_found, new_jobs, queries_processed, sources_scraped)
            VALUES (?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            total_jobs_found,
            len(all_new_jobs),
            len(job_titles),
            ", ".join(sources_used)
        ))
        conn.commit()
        conn.close()
        
        return {
            "run_date": datetime.now().isoformat(),
            "total_jobs_found": total_jobs_found,
            "new_jobs_count": len(all_new_jobs),
            "new_jobs": all_new_jobs,
            "queries_processed": len(job_titles),
            "sources_used": list(sources_used)
        }


def send_email_notification(summary: Dict, recipient_email: str):
    """
    Send email with Title + Company format
    """
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_PASSWORD")
    
    # Email subject
    subject = f"🎯 {summary['new_jobs_count']} New Technical Product Management Jobs in Willow Grove Area"
    
    # Email body with Title + Company format
    body = f"""
Job Alert - {datetime.now().strftime('%B %d, %Y')}
Location: Willow Grove, PA (40 mile radius)

{'='*70}
SUMMARY
{'='*70}
Total Jobs Found: {summary['total_jobs_found']}
New Jobs: {summary['new_jobs_count']}
Job Boards Searched: {', '.join(summary['sources_used'][:5])}

{'='*70}
NEW JOBS (Title + Company)
{'='*70}

"""
    
    # Group jobs by source for better organization
    jobs_by_source = {}
    for job in summary['new_jobs']:
        source = job.get('source', 'Unknown')
        if source not in jobs_by_source:
            jobs_by_source[source] = []
        jobs_by_source[source].append(job)
    
    # Format: Title + Company
    for source, jobs in jobs_by_source.items():
        body += f"\n📌 {source}\n"
        body += "-" * 70 + "\n"
        
        for i, job in enumerate(jobs[:20], 1):  # Limit to 20 per source
            body += f"{i}. {job['title']} + {job['company']}\n"
            body += f"   Location: {job['location']}\n"
            body += f"   Salary: {job['salary']}\n"
            body += f"   Apply: {job['url']}\n\n"
        
        if len(jobs) > 20:
            body += f"   ... and {len(jobs) - 20} more from {source}\n\n"
    
    body += f"\n{'='*70}\n"
    body += f"Total new opportunities: {summary['new_jobs_count']}\n"
    body += f"Database updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    body += f"{'='*70}\n"
    
    # Send email
    try:
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        
        print(f"✉️  Email sent successfully to {recipient_email}")
        return True
    
    except Exception as e:
        print(f"❌ Email error: {e}")
        return False


if __name__ == "__main__":
    # TECHNICAL PRODUCT MANAGEMENT JOB TITLES FOR COURTNEY
    JOB_TITLES = [
        "Digital Product Owner",
        "Product Marketing Manager",
        "Growth Product Manager",
        "Digital Marketing Manager",
        "Scrum Product Owner",
        "Technical Product Manager",
        "E-commerce Manager",
        "Product Owner Digital Channels",
        "Marketing Technology Product Owner",
        "Growth Architect"
    ]
    
    RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL", "your-email@example.com")
    
    # Run the agent
    agent = MultiJobBoardAgent()
    summary = agent.run_daily_scrape(JOB_TITLES)
    
    # Always send email (even if 0 new jobs for confirmation)
    send_email_notification(summary, RECIPIENT_EMAIL)
    
    # Save summary
    with open("scrape_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    
    print("\n✅ All done! Check your email.")
