from typing import List, Dict, Union, Any

def word_count_prompt1(
    word_count: str,
    # outline: List[Dict],
    outline: Union[Dict[str, Any], List[Dict[str, Any]]],
    title: str
    ) -> str:
        """Generate prompt for creating blog outline."""
        
        system_prompt = """
        Act as a seasoned content analyst with years of experience in writing and understanding SEO-friendly blogs.
        """
        
        prompt = f"""

Input:
1. Word Count:{word_count}
2. Outline: {outline}
3. Topic: {title}

Goal:

1. Calculate section-wise word count: Follow the process given below and give output in the specified format.

Process:

1. Step 1, Dissect the outline in the following sections. Do not forcefully give word count for a section which does not exist. If a section doesn’t exist return “N/A”:
a. Introduction: Introduction section will be explicitly labelled as 'Introduction' in the outline. Do not assume any other section as an introduction.
b. Overview: Overview is a part of the blog aimed at providing basic information about the topic.
c. Core read: The core read section of a blog is the meaty part of the blog which answers the core question set out in the title.
d. Conclusion: Conclusion is the section of a blog which provides the reader with a summary and leaves them thinking about the information found in the blog.
e. FAQ
2. Step 2, Allot the sections a weightage percentage as follows:
a. Introduction- 7%
b. Overview- 8%
c. Core read- 65%
d. Conclusion-8%
e. FAQ- 12%
3. Step 3, Generate a random number between 1.000 and 1.199
4. Step 4, Multiply the weightage percentage given in Step 2 with the random number generated in Step 3.
5. Step 5, Multiply the word count mentioned in the input with the new sectional percentages generated in Step 4.
6. Step 6, If a particular section doesn’t exist in the outline then allocate its word count to the core read.
7. Step 7, Sometimes the overview will not be explicitly mentioned in the outline and will have to be ascertained by you whether a particular section plays the role of giving the overview to the reader.

Output: 
1. Give output in the following format: Introduction: Word Count, Overview: Word Count, Core read: Word Count, Conclusion: Word Count, FAQ: Word Count
2. Do not give any additional comments.
3. Do not give any calculations.
4. Give output in JSON format.
5. Do not write ```json in your response.
6. Give response in this format:

  "Introduction": 122,
  "Overview": 139,
  "Core read": 1129,
  "Conclusion": 139,
  "FAQ": 208


"""
        return {"system":system_prompt,"user": prompt}