
import os
from src.lib.supabase import supabase

def check_opportunities():
    try:
        # Check ProUni 2025 count
        count_res = supabase.table("opportunities") \
            .select("id", count="exact") \
            .eq("opportunity_type", "prouni") \
            .eq("year", 2025) \
            .execute()
        
        print(f"Total ProUni 2025 opportunities: {count_res.count}")

        # Check a few samples
        sample_res = supabase.table("opportunities") \
            .select("id, cutoff_score, scholarship_type, concurrency_tags") \
            .eq("opportunity_type", "prouni") \
            .eq("year", 2025) \
            .limit(5) \
            .execute()
        
        print("Sample Opportunities:")
        for row in sample_res.data:
            print(row)

        # Check if there are any courses with ProUni
        course_check = supabase.table("opportunities") \
            .select("course_id") \
            .eq("opportunity_type", "prouni") \
            .eq("year", 2025) \
            .limit(1) \
            .execute()
        
        if course_check.data:
            course_id = course_check.data[0]['course_id']
            course_info = supabase.table("courses") \
                .select("course_name") \
                .eq("id", course_id) \
                .execute()
            print(f"Sample Course Name: {course_info.data[0]['course_name'] if course_info.data else 'Unknown'}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_opportunities()
