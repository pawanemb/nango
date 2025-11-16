from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel

class BlogGenerationRequest(BaseModel):
    blog_title: str
    outline: Union[Dict[str, Any], List[Dict[str, Any]]]
    primary_keyword: str
    keyword_intent: Optional[str] = None
    category: str
    subcategory: str
    word_count: str
    industry: Optional[str] = None
    # intent: Optional[str] = None
    target_audience: Optional[str] = None
    secondary_keywords: Optional[List[str]] = None
    country: Optional[str] = "in"

class SearchResult(BaseModel):
    title: str
    link: str
    content: str
    datePublished: Optional[str] = None

class BlogResponse(BaseModel):
    status: str
    message: str
    task_id: str
    intro_task_id: str
    section_task_ids: List[str]
    test: str

class BlogGenerationStatusResponse(BaseModel):
    status: str
    message: Optional[str] = None
    blog_content: Optional[str] = None
    search_results: Optional[List[SearchResult]] = None

class FAQ(BaseModel):
    question: str
class Section(BaseModel):
    heading: str

class BlogOutline(BaseModel):
    title: str
    sections: List[Section]
    conclusion: str
    faqs: List[FAQ]