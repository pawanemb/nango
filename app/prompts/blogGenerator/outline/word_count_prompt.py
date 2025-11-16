from typing import List, Dict, Union, Any

def word_count_prompt(
    word_count: str,
    # outline: List[Dict],
    outline: Union[Dict[str, Any], List[Dict[str, Any]]],
    title: str
    ) -> str:
        """Generate prompt for creating blog outline."""
        
        system_prompt = """
        Act as a seasoned content analyst with years of experience in writing and understanding SEO-friendly blogs. Your role is to assign the word count weightage to each heading and sub-heading of the outline mentioned in the input. You should do this by understanding the process and goals for this to assign the word count weightage to the sections based on their significance, relevance, and importance with respect to the blog title.
        """
        
        prompt = f"""

Input:

Word Count:{word_count}
Outline:{outline}
Title:{title}

Goals: 

1. Assign Word Count Weightage: Give the word count weightage for all the headings and sub-headings in the blog based on the word count input of the user. 

2. Dissect the blog and label it: Dissect the blog into various sections and label them as Overview, Core Read, Conclusion, and FAQ.

3. Follow the word count split instructions: Follow the word count split instructions mentioned below to take the reference for splitting the word count distribution for each heading and sub-heading. 

4. Assign word count weightage on the basis of the total word count: You must split the word count weightage on the basis of the total word count input by the user. This will ensure that the word count split meets the total word expectations of the users when generating a blog based on this. 

5. Understand the blog title and outline to assign weightage based on importance: Go through the entire blog outline and establish its relationship with the blog title to judge the importance of each section for distributing the word count weightage. 

6. Assign the largest portions to the core sections: Assign the largest word count weightage to the core headings and the sub-headings mentioned within them. 

7. Consider Overview merged into relevant sections: For a blog outline that does not have ‘Overview’ tagged as H2, merge the relevant sections in the outline as the overview section and assign the word count weightage to them accordingly. However, it is not compulsory that all blog outlines will have an overview section. For such a blog outline, ignore the word count weightage instruction for the Overview section and instead, distribute its weightage to the Core Reading Section.

8. Do not follow the absolute word count split instruction: Do not allot absolute word count weightage to the sections in the outline as per the instructions below. These are just for your reference and you must allot the weightage based on the range mentioned for the section. 

9. Assign the weightage to the Core Sections based on their importance: You must split the word count weightage to the sections in the Core Reading based on their importance and relevance to the reader. You must not take a defensive approach of assigning equal weightage to each section unless very necessary. You can also take the liberty to divide the core section as important core reading and other core reading for this. Each subheading must receive a proportional share based on significance. The total word count for the Overview section (including all headings categorized under it) must strictly remain within 5-10% of the total blog word count. If merging multiple sections into the Overview, ensure their combined word count does not exceed this range. Any excess must be reallocated to the Core Reading section.

10. Conclusion word count weightage must support conciseness: Assign the word count for the conclusion only to support conciseness and an impactful ending to the blog. 



Process:

Step 1, Read the entire blog outline. 
Step 2, Understand the blog title for building its relation with the blog outline. This will help you understand the importance and significance of each section in the blog. 
Step 3, Divide the blog into the following sections: Overview, Core Read, Conclusion, FAQs. If you do not find any of these sections in the blog then do not forcefully label a section for the sake of it.
Step 4, In cases where the Overview is not mentioned specifically, find if the relevant section is mentioned in the outline. If yes, then merge the instruction for the word count split with this particular section(s). 
Step 5, In cases where there is no Overview mentioned in the blog outline, merge its distribution to the core reading sections based on their importance.  
Step 6, Understand the word count requirement for the blog. 
Step 7, Split the word count weightage to support the word count requirement of the blog on the following basis:

For 1000 words: Give word count weightage split for 900 words with the following weightage %
Overview: 5% - 10% (50-100 words)
Core Reading: 65% - 70% (650-700 words)
Conclusion: 5% - 10% (50-100 words)
FAQs: 100 words approximately in total 

For 1500 words: Give word count weightage split for 1300-1400 words with the following weightage %
Overview: 5% - 10% (75-150 words)
Core Reading: 65% - 70% (975-1050 words)
Conclusion: 5% - 10% (75-150 words)
FAQs: 100 words approximately in total 

For 2500 words: Give word count weightage split for 2200-2300 words with following weightage %
	Overview: 5% - 7% (125-175 words)
Core Reading: 70% - 80% (975-1050 words)
Conclusion: 5% - 7% (125-175 words)
FAQs: 5% - 7% (125-175 words) 




Output:
Do not add any heading or sub-heading from your end. 
Do not mention the overview separately and analyse from the outline if it is mentioned, allot its word count accordingly.
Do not give reasonings for your word count split. 
Do not mention any explanation about the weightage split. 
Do not acknowledge your response. 
Do not make any additional comments to the response. 
Do not add a label of the dissection of the outline in your response and simply tag the word count allotment for the respective headings and sub-headings. 
Give the output in the array format with the assigned word count weightage mentioned for headings and sub-headings in this format:
sections: [
  {{
   heading_length: 200, 
    heading_body: 50,
    subsections: [
      {{ subheading_length: 75 }},
      {{ subheading_length: 75 }}
    ]
  }},
  {{
    heading_length: 300,
    heading_body: 100,
    subsections: [
      {{ subheading_length: 100 }},
      {{ subheading_length: 100 }}
    ]
  }}
]
Here, heading length is the combined word count weightage at the H2 level. It includes, heading body which is the word count that will go for the explanation of H2. and the content within the subsections are the H3s contained within their respective H2s.
Do not write ```json in your response. 
The total word count for the Overview section (including all headings categorized under it) must strictly remain within 5-10% of the total blog word count. If merging multiple sections into the Overview, ensure their combined word count does not exceed this range. Any excess must be reallocated to the Core Reading section.

"""
        return {"system":system_prompt,"user": prompt}