from typing import List,Dict

def blog_metrics_prompt(
        scrapped_page: str
    ) -> str:
        """Generate prompt for creating blog outline."""

        system_prompt = f"""
Role: 
You are a writing analyst who can understand the scrapped blog content and understand it thoroughly to derive useful insights and facts from the page which can be used as a reference to cite or use for a similar blog section that you would write. 
        """

        user_prompt = f"""
Input: 
Scrapped page:{scrapped_page}

Goals:
Extract the full blog content word by word: Extract the blog content from the scrapped blog page without making any changes to the content and formatting mentioned in it to give the output word by word as it is mentioned. 

Ignore non-content sections: Ignore non-content sections like images, cta, author bio, related posts, advertisement, company information etc. 

Extract important information: Find the key pointers of the blog and extract very important information from the blog which should be referred to a similar section in a separate blog for improving its authority. This can include, summarized information, research or statistics which is quotable or an important fact which improves the explanation of the related concept or idea. 

Classify the gathered information: On the basis of the gathered information, classify the information in any of the two categories: Citation Information, and Understanding Information. 
 Citation Information: This will only include stats, facts, figures and research which can be quoted verbatim to support any information and improve its authority. 
Understanding Information: This will include the information which can be used as a reference to give any argument, or explain any concept. This will include the information pieces which are not citation information. 

Process:

Step 1, Read the markdown text received to you word by word.
Step 2, Extract the blog content in the text format. 
Step 3, Do not make any judgments; don't omit any text from your part.
 Step 4, Ignore all the images and non-blog parts mentioned in the content.
Step 5, Read the entire blog content thoroughly.
Step 6, Segregate: Segregate the given information into the following two types based on its uses- Citation Information (Used for Citing Facts, Figures, and Quotes), Understanding Information (Used to understand the topic better).
Step 7, Keep the wording of the information intact, without making any character, letter, word or sentence changes from the text in the original source. 

Output:
Give the output in the plain text format only. 
Give only the Citation and Understanding Information in your response. 
Do not add any content from your side.
Do not make any additional comment from your side.
Do not acknowledge the completion of the task.
Give only the content part and ignore other sections. 
Do not stop processing until all the content mentioned in the scrapped page is covered in the response.
Do not give citations and understanding information for the sake of it. In cases where there is no citation or understanding information, give ‘Nil’ as output. 
Do not give anchor text links of the scrapped page in the final output. 
Mention the page link of the website and its name in the response before the information. 
"""
        return {"system": system_prompt, "user": user_prompt}