from typing import List,Dict
from datetime import datetime
def inspiration_and_creative_prompt(
        blog_title: str,
        primary_keyword: str, 
        secondary_keywords: List[str],
        keyword_intent: str,
        industry: str,
        word_count: str, 
        country: str,
        category: str,
        subcategory: str,
        project: Dict
    ) -> str:
        """Generate prompt for creating blog outline."""
        secondary_keywords_str = ", ".join(secondary_keywords) if secondary_keywords else ""
        age_groups_str = ", ".join(project["age_groups"]) if project["age_groups"] else ""
        gender_str = ", ".join(project["gender"]) if project["gender"] else ""
        language = ', '.join(project.get('languages', [])) if project and project.get('languages') else 'English (UK)'
        current_date = datetime.now().strftime("%Y-%m-%d")
        prompt = f"""
Input
Primary Keyword: {primary_keyword}
Secondary Keywords: {secondary_keywords_str}
Blog Category: {category}
Blog Sub-Category: {subcategory}
Intent: {keyword_intent}
Word Count: {word_count}
Target Audience_Age: {age_groups_str}
Industry: {industry}
Title: {blog_title}
Target Language: {language}
Keyword Location: {country}
Target Gender: {gender_str}
Current Date: {current_date}

Goals
Create a blog outline that achieves the following goals in your response :
Audience-focused: Adjust the complexity of information based on the reading grade of the audience. For example, if the target audience for the blog for the primary keyword ‘ai trends’, is school-going kids studying, lying between the age of 12-15 years, then the expectation of the reader would be to have surface-level information about the concepts, just to get the awareness on the subject. On the other hand, if the audience is falling in the age group of 25-40 years, then they are expecting very precise, accurate, and actionable information. Hence the sub-headings have to go beyond surface-level explanations in this case, assuming that the readers already are aware of it and they are looking for a credible source to expand their knowledge.
Well-structured: Ensure a natural reading experience. All headings and sub-headings must be organized in a logical way. Do not go off-topic. If you are writing a blog about a historical event, it makes sense to have headings or sub-headings appear in chronological order. If you are writing a blog to improve a law, it makes sense to have headings or sub-headings appear in the order of steps one would have to take. If you are writing a blog about fashion tips, it makes sense to group these tips by objective like makeup tips, party wear tips, accessory tips, etc.
Alignment with intent: Ensure that the blog sub-headings are aligned with the intent of the blog and must solve the problem of the users specific to their intent. 
For example, if the blog is of Informational intent, then it must provide clarity, explanations, or background of the concepts. For e.g., if the blog is about “What is Digital Marketing”, then the blog sub-headings must be to explain the concepts related to it. 
Similarly, if it is of Navigational intent, then it must guide users to specific and targeted solutions. For eg., if the blog title is about ‘iPhone pricing’, then the user must receive the various pricing options as the user is already beyond the need for getting surface-level explanations. 
For Commercial intent, it must help users compare, evaluate, or make decisions. For e.g., for the blog topic "SEO vs. SEM: Which Strategy Suits Your Business?", blog sub-headings must list the advantages and disadvantages for both as the users are in the decision-making stage. 
For Transactional intent, the outline must direct users toward action-oriented content. For e.g., "How to Optimize Your Website for SEO in 5 Steps", provides clear steps for achieving this in the sub-headings. This alignment has to be further based on the category and sub-category of the blog which are based on the user selections, and clearly tells about the kind of sub-headings the users are expecting. For e.g., in a blog titled “How to Create a Sales Plan?”, the blog is of the ‘Action-Oriented’ category and ‘How-To sub-category’. For this blog, the sub-headings must give clear actionable steps for creating the sales plan and can avoid the surface-level sub-headings like What is a sales plan, Importance of Sales Plan, etc.  
Inclusion of Primary and Secondary Keywords: Ensure that the blog outline incorporates the primary and secondary keywords as received in the input to ensure coverage of the concepts. By doing this, the blog sub-headings must directly solve the problem of the users, and avoid incorporating abstract ideas, and vague and redundant sub-headings as they are not useful and helpful to the reader. Also, make sure that the keywords are included naturally within the sub-headings, and the compulsive stuffing of keywords is not done for the sake of SEO optimisation as it hampers the reader’s trust in the blog.  For eg., a blog with the primary keyword of AI trends, and secondary keywords of Gen AI, Machine Learning, and NLP, highlights the need of the user to study the trends with respect to the latest advancements. 
Include unique perspectives: Make sure that all the headings and subheadings support the in-depth coverage of content on the blog. In doing this, ensure that all the headings and subheadings support a unique perspective that the readers might not find otherwise and are solving their problem. Based on this, give only the most important subheadings in the outline, which fit the word count constraints of the blog. For eg., for the blog titled “How to Overcome Audio Quality Issues with Wireless Studio Monitor Headphones”, with a word count limit of 1000 words, prioritise giving the most important suggestions for the problem while doing justice to the word count limit. Hence, avoid giving filler sub-headings like ‘Importance of Headphones’, ‘About Headphones’, etc.
Apt Outline breakdown: Include Main Sections (further broken down in headings and sub-headings via H2, H3), Conclusion, and FAQs. Give a Conclusion before the FAQs and always keep the FAQs at the last of the outline section.
Choose the right H2 and H3: Understand the title and lay more emphasis on important topics and reduce emphasis on unimportant details. Do not include redundant details. Do not repeat information unless absolutely necessary. Do not include examples and case studies as separate headings unless the blog title talks about the need for it. 
Adherence with EEAT guidelines: Ensure the outline includes sub-headings that help the blog adhere to the E-E-A-T (Experience, Expertise, Authoritativeness, and Trustworthiness) principles. This principle entails the need for creating relevant and quality blogs as search engines like Google evaluate content based on this principle for ranking the content. To achieve this, you must focus on creating outline sections that bring value to readers and match their interests. To evaluate the interest of the readers with respect to any blog post, establish the relationship between the primary and secondary keywords selected by the users and further understand the intent of the keywords (especially the primary keyword) and understand its synergy with the category and the sub-category selected by the user for producing the content. By doing this you can integrate elements that establish subject matter expertise and credibility throughout the outline.

Understand Language Preference: Understand the language preference of the blog text between English (UK) and English (USA). You must write the content based on this only. For example, if the user has selected English (UK) as their language preference, then words like 'recognize' must be written as 'recognise' to support the preference.

 Use Simplified Language:  The tonality of the sub-headings must be direct and must avoid unnecessary complex wordings. Replace complex phrases with simpler alternatives to improve relatability. Here are a few examples of that: In order to → To; Despite the fact that → Although; Leverage → Use; Utilize → Use, Subsequent → Next, following; Commence → Start, begin; Terminate → End, stop; Ascertain → Find out, determine; Facilitate → Help, ease, enable; Expedite → Speed up, accelerate; Implement → Carry out, apply, put in place; Disseminate → Share, spread; Mitigate → Reduce, lessen, ease; Enumerate → List, count; Comprehend → Understand, grasp; Obtain → Get; Procure → Get, acquire; Endeavor → Try, attempt; Illustrate → Show, explain; Indicate → Show, point out; Demonstrate → Show, prove; Substantial → Large, significant; Adequate → Enough, sufficient; Pertinent → Relevant, related; Consolidate → Combine, merge; Constitute → Make up, form; Rectify → Fix, correct; Optimize → Improve, make better; Articulate → Express, explain; Negate → Cancel, undo; Presume → Suppose, assume; Attain → Reach, achieve; Allocate → Give, assign; Engage in → Take part in, do; Accomplish → Complete, achieve; Contemplate → Think about, consider; Scrutinize → Examine, check; Advocate → Support, recommend; Enhance → Improve, boost; Elicit → Draw out, bring out
Giving Useful, Credible, and Relevant Information in Sections: Alignment with the E-E-A-T principles is a must. You must ensure that all the heading and sub-heading level information is factually correct, credible, and updated as if the expert on the subject has written about it.  The section headings should go beyond surface-level topic suggestions unless very necessary. 

For all blogs with titles that include words such as “steps”, “process”, “guide”, "how to", “do's and don'ts”, or “shortcuts”, strictly avoid any top-of-the-funnel section headings such as attempt to explain ‘why it is important’, ‘what it is’, or ‘why you should do it’ as separate H2s.
Start ONLY with the main process or the first relevant step. Skip any and all conceptual outlines unless very necessary.
Give headings and sub-headings which supports interactive formatting options: Give headings and sub-headings which apart from supporting text supports interactive formatting options upon writing the blog. These include:
i. Lists


Bulleted lists (•)
Numbered lists (1, 2, 3)
Checklists (✓)
Nested lists


ii. Tables


Simple 2-column tables (term vs definition)
Multi-column tables (side-by-side comparisons)
Highlighted rows and columns for emphasis


iii. Block Formatting
Blockquotes (“ ”)
Pull quotes
Code blocks (for technical content)


iv. Text Emphasis


Bold for keywords/numbers
Italics for subtle emphasis
Monospace for commands/filenames
Occasional ALL CAPS / small caps for emphasis


v. Dividers & Breaks


Section dividers (•••)
Pros vs Cons lists
Timelines (Year → Event)
n. Do not give the predictable number of sub-headings in the outline: Avoid taking a templatised approach of giving the same number of sub-headings for all the heading sections. The number of sub-headings must be logical as per their respective heading section name. Vary the number of sub-headings sections thus wherever possible. Try to bring variance for every consecutive heading. However, in doing this, prioritise the comprehensiveness of information to cover through the outline. This is critical for the success of the task and the test of your ability. 
o. Multi-intent coverage: Structure the outline to serve clusters of intents across AI, search, and social. Each main section must map to one micro-intent: informational, comparative, transactional, or community-driven. Avoid keyword-only thinking—optimise for entities and relationships.


o. Prioritise the usage of active voice and present tense in your response: Make sure to keep the headings and sub-headings interactive and participative. Prioritise the usage of active voice and present tense in the headings and sub-headings section name. 
p. Take a direct approach in giving the subsections heading, directly indicating what the readers will find in this section. Keep the character limit restrained for sub-headings to 30 characters at max. Ignore this instruction only when very necessary.
q. Break the predictable pattern of giving the same number of subsections for the heading. Take a natural approach of giving a diverse number of subsections depending on its heading. Do this in such a way that is highly relevant to the heading and does not contain any unnecessary subsections that might not be required. Follow this instruction very strictly as it is a direct test of your ability to perform this task. 

Process:

Step 1, Understanding Primary and Secondary Keywords and their Role: You must ensure that the primary keyword and the secondary keywords are included in the blog headings and sub-headings. For this, it is important that you incorporate these keywords naturally within the headings and subheadings to establish a natural connection with the users. The usage of the secondary keywords must complement the primary keyword and guide the writers to include information about the primary keyword with context. For example, if a primary keyword is ‘AI trends’, and the secondary keywords for the post are ‘Generative AI’, ‘NLP’, ‘Open Source LLMs’, etc., then the sub-headings must have a clear focus on writing the headings and subheadings that most importantly focuses on the AI trends and include the sub-headings mentioned as the secondary keywords as they are the most important and relevant to the primary keyword ‘AI trends’. 

Step 2, Create an Outline for an Inspirational and Creative Category Blog: To do this, you must understand the purpose of the category. Inspiration refers to the idea which moves the thought process or emotions of anyone to think or act in a certain way. Creativity on the other hand uses imagination to come up with an idea or solution. When inspiration is combined with creativity, it can be used for uplifting someone or to spark an idea. Thus, the idea of this blog category is to inspire readers or motivate them to think creatively. The blogs in this category connect with the readers at a deeper level. Readers of this blog category get a fresh perspective, and get a sense of possibility to achieve something. The blogs in this category move beyond the foundational understanding of concepts, and focus on giving the reader something fresh and innovative that they might even miss with sound knowledge of the concept or experience in the discipline. For example, for a blog talking about ‘inspiring and creative ways to write’, the readers of the blog would be beginners and seasoned writers alike. Furthermore, they may be already aware of the fundamentals of writing well, but might read this blog to cure their writer's block. Hence, such a blog must give fresh reasons to write like ‘writing clears your mind’, ‘reflection of a writer’s own personal challenge and the way he/she dealt with it’, ‘stories of great writers who faced it and how their weird habits helped them get out of it’ etc. 
They are more like Ted Talks, and less like a blog dealing with strategic and analytical ways of accomplishing something. Thus, these blogs are impactful and are not written with the intent of driving decision-making or getting an elementary or advanced level knowledge of the concept. 


Dos for creating the blog outline for inspirational and creative category:

Understand the target audience and their specific needs: Understand the specific needs of the target audience with context to the title of the blog. Assess the need for inspirational or creative ideas based on it. Build on those ideas sequentially through headings and sub-headings and inspire readers to adopt the learnings of the blog in their daily life. For example, for the blog talking about ‘Inspiring Ways to Overcome Obesity’, motivate readers to adopt a healthy lifestyle and go to the gym. A surface level explanation of ‘what is obesity’, will not do the job as the readers might be already aware of it. In such cases, inspire the readers to acknowledge the problem and give them an action plan to face the challenge. Also take a unique stance busting the common misconceptions of going to gym. This will inspire the readers to start taking initiatives for a healthier lifestyle. 

Alignment with the Title: Maintain direct alignment with the title in giving the headings of the blog. Include ideas only relevant to the title's context and the reader’s interest. For example, for a blog talking about the ‘journey of becoming a writer’, you cannot talk about ‘AI writing tools’ in the market as it is not closely related to the topic and a different point of discussion. 

Be mission oriented: After understanding the problem statement of the reader, cause the readers to reflect on why thinking or acting a certain way is important to address the challenge. Give headings and sub-headings that align with this framework. This will keep the readers focused and engaged and also possibly improve their lives.  

Empathise with users: You must be sensitive to the needs of the users and maintain a balanced tonality which is neither very formal, nor very casual. For example, for the blog talking about the ‘journey of learning Chinese’, you cannot have the heading 'Crucial Methodologies to Adopt to Become Proficient in Chinese’, or “Here’s How You Can be a Chinese Pro Max”. Doing this will either intimidate the user, or break their trust with overly candid messaging. A heading with a balanced tonality like - “Step-by-step Approach You Can Take to Learn Chinese”. This will resonate with the reader well as they can consume it anytime, anywhere.  

Focus on Impact: You must focus on giving headings and sub-headings which leave a lasting impact in the lives of the readers. Including only surface-level details or over complex subjects can dilute the impact. Focus on giving actionable advice, and determine if the heading or sub-heading leaves an actual impact. For example, for a blog article talking about ‘innovative AI applications’, talk about the solutions which businesses might miss and focus on its practical application. In this case you can talk about how ‘using AI agents for the business in a certain industry can cut down their cost’. Doing this, you must ensure that you don’t give an in-depth or analytical explanation of the concept. 

Keep the information factually correct and take real life examples: You must only include the information which are factually accurate and can be backed up with sound logic. This will  make the blog article less subjective, and more thoughtful and credible. You can take the liberty of adding real life examples especially in the sub-headings to prove a point. However, these must be strictly real life examples which can be tracked with the source. 

Build the narrative logically: Your headings and sub-headings will directly reflect the narrative of the writer for addressing the challenge in the reader's life. Make sure that these are logically broken down with the simpler chunks of headings and sub-headings. For example, for the blog talking about overcoming verbosity in writing, you cannot stress about why verbose writing looks bad after you have told the ways to overcome verbosity.


 
Don’ts for creating the blog outline for inspirational and creative category:

Don’t take a moral ground: You must not enforce moral ideas in your headings and sub-headings unless very necessary. For example, for a blog talking about the ‘journey of becoming a good writer’, you must only focus on ‘who is a good or bad writer, and what one can do to ‘improve their writing’. Telling the readers that ‘this blog is ‘only for dreamers, believers, and hustlers’, will discourage the widespread readership of the blog. However, for blogs talking about issues like’ climate change, diversity, fairness’, you can take the moral ground as they do not express the personal opinions of the reader and the views can be backed with strong research in the field.  

Don’t focus on headings and sub-headings which only provides strategies and analysis but not an actionable value: Your blog headings and sub-headings must evoke thought and ideas. Catering merely to the awareness needed will not do justice to this blog type and the expectation of readers. 

Don’t indulge in personal biases: You cannot take the liberty of imposing your personal beliefs. For example, for a blog talking about the ‘journey of becoming a good writer’, you cannot tell the reader ‘that bad writers are a burden to society’. This view is subjective and enforces the writer’s personal belief without any substantial evidence. 

Don’t be promotional: You cannot advocate any product, brands or service in the heading and sub-headings of this blog category. Giving a promotional touch in this category of blog will impact the credibility of the blog. 

Don’t include false examples and case studies: Don’t take the liberty of giving false examples and case studies which cannot be tracked to its original source. Doing this will damage the authenticity of the blog and the writer. 

Don’t be over enthusiastic, build the narrative naturally: Don’t jump to conclusions, don’t make assumptions and don’t drive a frenzy in the reader's mind. Give readers enough time to naturally build their interest in blog and apply the learnings. Setting narratives for a blog topic talking about the ‘inspiring reasons to lose belly fat’ cannot be set on the premise ‘lose your belly now’.  

Don’t include complex concepts: Don’t include the headings and sub-headings which are overly complex. The headings and the sub-headings in this blog category must only talk about the actionable ways of achieving something. Any complex concept which does not directly talk about it will lose the reader's interest. 

Don’t build on basic and foundational concepts: The readers of this blog category have the fundamental understanding of the concept. The reason for choosing to read a blog in this category is to get out of the box creative and inspiring ideas to know something. Hence don’t include surface level information. 

Don’t be emotional: Don’t be emotional in your messaging. Let the readers digest the content through headings and sub-headings and naturally build an interest in the blog. 

Don’t be misleading: Ensure that your blog headings and sub-headings do not include elements which can mislead the readers. For example, for a blog talking about the ‘journey of becoming a pilot’, you cannot have headings like ‘Proven Ways of Becoming a Pilot’, or ‘Becoming a Pilot is Very Easy’. 

Don’t repeat information: Don’t repeat information in the headings and sub-headings of the blog. Cover an issue one step at a time in the outline and avoid redundancies. 

Don’t include an exclusive piece of information in the sub-headings: Don’t give the sub-headings which are not directly aligned with its heading. The sub-headings must only complement the heading and explain its concept in an easier and broken down manner.  

Step 3: Direct Alignment with the Blog Title: You must factor in the title of the blog to directly understand the user’s expectations from the blog. You must give the blog headings and sub-headings based on this only and do not include any redundancies and vagaries. Furthermore, you must ensure that the blog headings and sub-headings must uniquely address the concepts relating to the title and you do not repeat any heading and sub-heading unless very necessary. For instance, if the blog title is “10 Most Important Tools in Email Marketing”, then your focus must be on giving the list of such tools in the sub-headings irrespective of the word count instructions you receive. Likewise, if the blog title is about “What is Digital Marketing”, then your headings and subheadings must be to ensure that the readers are able to understand the concept by answering the query in the title directly. 
 
Step 4: Maintaining Word Count Instructions: Ensure that the number of H2s strictly matches the word count criteria. Always validate the count before returning the final output.
 Sub-heading Count Based on Word Count:
For 350 words:  
Sritctly include only 1 H2.
Include  a maximum of 3 most important H3s, directly addressing the concept or query mentioned in the title. 
Do not cover the foundational understanding of the topic unless required.
Override the number of H3 instruction if the blog title includes a fixed number (e.g., '10 tools', '5 steps' etc.) and give the outline accordingly.
For 850 words: Strictly include only 1-2 H2s 
For 1250 words: Strictly include only 2-3 H2s 
For 2000 words: Strictly include only 3-5 H2s
Make sure that each sub-heading you give supports a minimum of 50 words and a maximum of 250 words such that the information mentioned within it is written by a human without any fillers and redundancies for giving the most valuable information to the readers aligned with the E-E-A-T principles of writing helpful content. 
For all blogs with titles that include words such as “steps”, “process”, “guide”, "how to", “do's and don'ts”, or “shortcuts”, DO NOT include any introduction-style or top-of-the-funnel explainers like 'Why this is important', or 'What this means'. Start ONLY with the main process or the first relevant step. Skip any and all conceptual outlines.
Prioritise the importance of concepts to be included in the headings and sub-headings based on the word count and give the most important sections only with respect to the word count. 
If the blog title includes a fixed number (e.g., '10 tools'), override word count logic and give exactly that number of H2s. Otherwise, enforce H2 count strictly based on the word count.
For example, for a blog talking about ‘6 ways to improve digital marketing’, give 6 H2s even if the word count selection is of 1000 words. Furthermore, ensure that the reason why the number is mentioned in the title of the blog is fully catered. For example, for a blog talking about the ‘6 ways to improve your digital marketing’, make sure you give 6 ways in H2, apart from including other H2s like Introduction, Conclusion etc. 
Step 5: Ensuring the Ease of Reading: To ensure ease of reading, do not apply the formulaic approach of creating H3 level sub-headings for every H2 level heading. This is to ensure that only the most important sub-headings are given in the output and the scope of redundancies is reduced. For instance, you can skip H3 level headings which offer only top-of-the-funnel explanations of the concepts.  For eg., the blog sub-heading about ‘What is Digital Marketing’ might not require further sub-headings as the users are simply expecting the answer to this question.

Step 6: User-Friendly Language: Avoid the usage of words with more than three syllables in the headings and sub-headings. This will ensure that the headings and sub-headings are easy to read. However, make exceptions for primary and secondary keywords as they have to be used as it is in the content and their headings and sub-headings. The objective of this is to ensure that the headings and subheadings speak to the reader and are engaging. Furthermore, the verb usage in the headings and sub-headings must prioritise ‘action verbs’ over ‘thinking verbs’. 
Step 7: Heading and Sub-heading Character Limit: Maintain the character limit of 65 characters for all the headings so that the readers are able to digest them and are able to recall them even in a skim reading on a device like a mobile phone.  In doing this, make sure that all the section sub-headings are less than 45 characters, directly telling what this section will do. 


Step 8: The blog Outline Structure has to be the following: 
Sections (Numbers depending on the word count), Conclusion, FAQs. Maintaining this structure ensures that the blog outline is properly formatted and the blog looks complete.  The users must not be left wondering - ‘what next’, or ‘why this’. 
Do not include the Introduction as the heading in the outline response as it looks redundant and self-explanatory. Thus, begin directly with the section headings arranged chronologically, following a logical order and then include FAQs at the end followed by a Conclusion.



Step 9: FAQs: Do not give FAQs before the conclusion. FAQs. Ensure that FAQs are popular questions related to the blog title. Ensure they cover both basic and advanced doubts. To determine which question is more relevant, think about what questions might a person think about when they are about to implement the knowledge they just learnt in the blog. Do not answer the FAQs. The structure of FAQs should be such that the density of primary keywords is maintained at 1% and furthermore the secondary keywords are included, building a natural connection with the readers. Include 3-6 FAQs in the response. However, for the word count input of 350 words, give a maximum of 3 FAQs. Make sure to include the FAQs, whose answer provides the latest and updated information. FAQs should only and only be given after the conclusion.
Output:	
Give the output in the JSON format.
Do not give explanations of the headings and subheadings.
Do not acknowledge the completion of the task in your response. 
Give FAQs after the conclusion.
Give Conclusion before the FAQs.
When giving output, do not write "```json" or "```"
Remove the markdown formatting and other special symbols from the output. 
Do not include em dash (—) and n-dash ( – ) anywhere in your response strictly. This is critical for the success of the task.
Don’t give numbers to headings or subheadings in your response.




Please provide the outline in the following JSON format:
{{
  "sections": [
    {{
      "heading": "Main Section Heading",
      "subsections": [
        "Subsection 1",
        "Subsection 2",
        "Subsection 3"
      ]
    }}
  ],
  "conclusion": "Conclusion Title",
  "faqs": [
    "Relevant FAQ Question 1",
    "Relevant FAQ Question 2",
    "Relevant FAQ Question 3"
  ]
}}
"""
        return prompt