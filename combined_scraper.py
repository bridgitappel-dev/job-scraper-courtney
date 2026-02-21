"""
Combined Job Scraper for Courtney
Uses BOTH The Muse and Adzuna APIs for maximum coverage
"""

import requests
import json
from datetime import datetime
from typing import List, Dict
import os
import time


class CombinedJobScraper:
    """Combined scraper using The Muse + Adzuna"""
    
    def __init__(self, adzuna_app_id: str = None, adzuna_app_key: str = None):
        self.adzuna_app_id = adzuna_app_id
        self.adzuna_app_key = adzuna_app_key
        
    def scrape_muse(self) -> List[Dict]:
        """Scrape The Muse (no API key needed!)"""
        
        print("\n" + "="*60)
        print("SCRAPING THE MUSE")
        print("="*60)
        
        base_url = "https://www.themuse.com/api/public/jobs"
        all_jobs = []
        
        searches = [
            {"category": "Product Management", "level": "Mid Level"},
            {"category": "Product Management", "level": "Senior Level"},
            {"category": "Product Management", "location": "Remote"},
        ]
        
        for search_config in searches:
            print(f"\nSearching: {search_config}")
            
            for page in range(2):  # 2 pages = 40 jobs per search
                try:
                    params = {**search_config, "page": page, "descending": True}
                    response = requests.get(base_url, params=params, timeout=10)
                    response.raise_for_status()
                    
                    data = response.json()
                    jobs = data.get("results", [])
                    
                    if not jobs:
                        break
                    
                    for job in jobs:
                        company = job.get("company", {})
                        locations = job.get("locations", [])
                        location_str = ", ".join([loc.get("name", "") for loc in locations])
                        
                        parsed = {
                            "id": f"muse_{job.get('id')}",
                            "title": job.get("name", ""),
                            "company": company.get("name", "Unknown"),
                            "location": location_str or "Not specified",
                            "posted_date": job.get("publication_date", ""),
                            "url": job.get("refs", {}).get("landing_page", ""),
                            "description": job.get("contents", "")[:500],  # First 500 chars
                            "source": "The Muse"
                        }
                        all_jobs.append(parsed)
                    
                    print(f"  Page {page}: Found {len(jobs)} jobs")
                    time.sleep(0.5)  # Be nice to the API
                    
                except Exception as e:
                    print(f"  Error on page {page}: {e}")
                    break
        
        print(f"\n✅ The Muse total: {len(all_jobs)} jobs")
        return all_jobs
    
    def scrape_adzuna(self) -> List[Dict]:
        """Scrape Adzuna (requires API key)"""
        
        print("\n" + "="*60)
        print("SCRAPING ADZUNA")
        print("="*60)
        
        if not self.adzuna_app_id or not self.adzuna_app_key:
            print("⚠️  Skipping Adzuna - no API credentials")
            print("   Get free credentials at: https://developer.adzuna.com/")
            return []
        
        base_url = "https://api.adzuna.com/v1/api/jobs/us/search"
        all_jobs = []
        
        searches = [
            {"what": "product manager", "where": "San Francisco"},
            {"what": "product manager", "where": "Remote"},
            {"what": "technical product manager", "where": ""},
            {"what": "senior product manager", "where": ""},
        ]
        
        for search_config in searches:
            print(f"\nSearching: {search_config}")
            
            for page in range(1, 3):  # 2 pages = 100 jobs per search
                try:
                    url = f"{base_url}/{page}"
                    params = {
                        "app_id": self.adzuna_app_id,
                        "app_key": self.adzuna_app_key,
                        "results_per_page": 50,
                        "what": search_config["what"],
                        "sort_by": "date",
                        "max_days_old": 30
                    }
                    
                    if search_config["where"]:
                        params["where"] = search_config["where"]
                    
                    response = requests.get(url, params=params, timeout=10)
                    response.raise_for_status()
                    
                    data = response.json()
                    jobs = data.get("results", [])
                    
                    if not jobs:
                        break
                    
                    for job in jobs:
                        location = job.get("location", {})
                        salary_min = job.get("salary_min")
                        salary_max = job.get("salary_max")
                        salary_str = None
                        
                        if salary_min and salary_max:
                            salary_str = f"${int(salary_min):,} - ${int(salary_max):,}"
                        
                        parsed = {
                            "id": f"adzuna_{job.get('id')}",
                            "title": job.get("title", ""),
                            "company": job.get("company", {}).get("display_name", "Unknown"),
                            "location": location.get("display_name", "Not specified"),
                            "salary": salary_str,
                            "posted_date": job.get("created", ""),
                            "url": job.get("redirect_url", ""),
                            "description": job.get("description", "")[:500],
                            "source": "Adzuna"
                        }
                        all_jobs.append(parsed)
                    
                    print(f"  Page {page}: Found {len(jobs)} jobs")
                    time.sleep(0.5)
                    
                except Exception as e:
                    print(f"  Error on page {page}: {e}")
                    break
        
        print(f"\n✅ Adzuna total: {len(all_jobs)} jobs")
        return all_jobs
    
    def scrape_all(self) -> List[Dict]:
        """Scrape from all sources"""
        
        print("\n" + "="*60)
        print("COMBINED JOB SCRAPER FOR COURTNEY")
        print("="*60)
        print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Scrape both sources
        muse_jobs = self.scrape_muse()
        adzuna_jobs = self.scrape_adzuna()
        
        # Combine
        all_jobs = muse_jobs + adzuna_jobs
        
        # Remove duplicates (same title + company)
        unique_jobs = {}
        for job in all_jobs:
            key = f"{job['title']}_{job['company']}".lower()
            if key not in unique_jobs:
                unique_jobs[key] = job
        
        final_jobs = list(unique_jobs.values())
        
        print("\n" + "="*60)
        print(f"📊 RESULTS SUMMARY")
        print("="*60)
        print(f"The Muse:    {len(muse_jobs)} jobs")
        print(f"Adzuna:      {len(adzuna_jobs)} jobs")
        print(f"Total:       {len(all_jobs)} jobs")
        print(f"Unique:      {len(final_jobs)} jobs (after deduplication)")
        
        return final_jobs
    
    def filter_and_save(self, jobs: List[Dict]) -> List[Dict]:
        """Filter jobs by keywords and save"""
        
        # Keywords to look for
        include_keywords = [
            "product manager", "product management", "pm",
            "roadmap", "platform", "technical product"
        ]
        
        exclude_keywords = [
            "junior", "entry level", "intern",
            "marketing product", "sales"
        ]
        
        filtered = []
        for job in jobs:
            text = f"{job['title']} {job['description']}".lower()
            
            has_include = any(kw.lower() in text for kw in include_keywords)
            has_exclude = any(kw.lower() in text for kw in exclude_keywords)
            
            if has_include and not has_exclude:
                filtered.append(job)
        
        print(f"\n🎯 After keyword filtering: {len(filtered)} jobs")
        
        # Save to file
        output_file = f"daily_jobs_{datetime.now().strftime('%Y%m%d')}.json"
        with open(output_file, 'w') as f:
            json.dump(filtered, f, indent=2)
        
        print(f"💾 Saved to: {output_file}")
        
        # Also save to the standard filename for the application agent
        with open("daily_jobs.json", 'w') as f:
            json.dump(filtered, f, indent=2)
        
        print(f"💾 Also saved to: daily_jobs.json (for application agent)")
        
        # Print samples
        if filtered:
            print("\n📋 SAMPLE JOBS:")
            print("="*60)
            for i, job in enumerate(filtered[:5], 1):
                print(f"\n{i}. {job['title']}")
                print(f"   Company: {job['company']}")
                print(f"   Location: {job['location']}")
                if job.get('salary'):
                    print(f"   Salary: {job['salary']}")
                print(f"   Source: {job['source']}")
                print(f"   URL: {job['url'][:70]}...")
        
        return filtered


def main():
    """Main function"""
    
    # Get Adzuna credentials from environment (optional)
    adzuna_id = os.getenv("ADZUNA_APP_ID")
    adzuna_key = os.getenv("ADZUNA_APP_KEY")
    
    # Create scraper
    scraper = CombinedJobScraper(adzuna_id, adzuna_key)
    
    # Scrape all sources
    jobs = scraper.scrape_all()
    
    # Filter and save
    filtered = scraper.filter_and_save(jobs)
    
    print("\n✅ Done!")
    return filtered


if __name__ == "__main__":
    main()
