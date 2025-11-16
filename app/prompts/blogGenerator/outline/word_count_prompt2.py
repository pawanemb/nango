from typing import List, Dict, Union, Any
def word_count_prompt2(
    word_count: str,
    # outline: List[Dict],
    outline: Union[Dict[str, Any], List[Dict[str, Any]]],
    title: str,
    count1: Dict[str, Any]
    ) -> str:
        """Generate prompt for creating blog outline."""
        system_prompt = """
        Act as a seasoned content analyst with years of experience in writing and understanding SEO-friendly blogs.
        """
        outline_response = """{
  "Introduction": {
    "wordCount": 119
  },
  "Overview": {
    "wordCount": 119
  },
  "CoreRead": {
    "Understanding Digital Marketing": {
      "headingWordCount": 50,
      "subHeadings": {
        "Definition and Scope": 47,
        "Importance in the Modern Business Landscape": 47
      }
    },
    "Key Components of Digital Marketing": {
      "headingWordCount": 50,
      "subHeadings": {
        "Search Engine Optimization (SEO)": 47,
        "Content Marketing": 47,
        "Social Media Marketing": 47,
        "Pay-Per-Click Advertising (PPC)": 47,
        "Email Marketing": 47,
        "Affiliate Marketing": 47,
        "Influencer Marketing": 47
      }
    },
    "Benefits of Digital Marketing": {
      "headingWordCount": 50,
      "subHeadings": {
        "Cost-Effectiveness": 47,
        "Targeted Audience Reach": 47,
        "Measurable Results and Analytics": 47,
        "Higher Engagement and Conversion Rates": 47
      }
    },
    "Challenges in Digital Marketing": {
      "headingWordCount": 50,
      "subHeadings": {
        "Constant Algorithm Changes": 47,
        "Increased Competition": 47,
        "Privacy Regulations and Compliance": 47,
        "Content Saturation": 47
      }
    },
    "Future Trends in Digital Marketing": {
      "headingWordCount": 50,
      "subHeadings": {
        "AI and Automation in Marketing": 47,
        "Voice Search Optimization": 47,
        "Personalization and Customer Experience": 47,
        "The Rise of Short-Form Video Content": 47
      }
    }
  },
  "Conclusion": {
    "wordCount": 136
  },
  "FAQ": {
    "headingWordCount": 40,
    "subHeadings": {
      "What is digital marketing and why is it important?": 54,
      "How does SEO contribute to digital marketing success?": 54,
      "What are the biggest challenges businesses face in digital marketing?": 55
    }
  }
}"""
        prompt = f"""
Role:
Act as a seasoned content analyst with years of experience in writing and understanding SEO-friendly blogs.
Input:
1. Section-wise word count:{count1}
2. Outline: {outline}
Goals:
1. Assign Word Count: Give the word counts for all headings and sub-headings.
.
2. Dissect the blog and label it: Dissect the various sections of the blog and label them as Overview, Core Read, Conclusion, and FAQ.
Process:
1. Step 1, Dissect the outline in the following sections. Do not forcefully label a section or create a section which does not exist. If a section doesn’t exist return “N/A”:
a. Introduction
b. Overview
c. Core read
d. Conclusion
e. FAQ
2. Step 2, allot the sections the word count as mentioned in the input.
3. Step 3, If any section doesn’t exist in the outline then divert its word count to the core read.
4. Step 4, Distribute the total word count of a section amongst all headings and sub-headings.
5. Step 5, You must understand that H2 body needs to have a dedicated word count as it is a separate body of text than the sub-headings under it. The word count of a section must be divided between the heading body and the sub-heading body.
6. Step 6, Do not give the heading body word count for FAQs and only give the word count for all the questions mentioned within it.
Output:
1. Do not give any additional comments.
2. Do not give any calculations.
3. Give response in the markdown format only
4. Do not give ```markdown``` in the response
3. Do not give any additional comments.
4. Do not give any calculations.
5. Give response in this format:
{outline_response}
"""
        return {"system":system_prompt,"user": prompt}