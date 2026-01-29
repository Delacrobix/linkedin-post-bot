"""
LangGraph workflow for generating LinkedIn post text.
"""

from typing import TypedDict

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

load_dotenv()


class PostState(TypedDict):
    title: str
    description: str
    body: str
    previous_posts: list[str]
    post_text: str


def generate_post(state: PostState) -> PostState:
    """Generate LinkedIn post text from article content."""
    llm = ChatOpenAI(model="gpt-5-mini", temperature=0.7)

    previous_posts_section = ""
    if state["previous_posts"]:
        posts_text = "\n---\n".join(state["previous_posts"])
        previous_posts_section = f"""
            Here are my most recent LinkedIn posts. Avoid repeating similar openings, structures, or phrases:
            {posts_text}
        """

    prompt = f"""You are writing a LinkedIn post as the author of a technical article.
        Write in first person as if YOU wrote this article and want to share it with your network.

        Article Title: {state["title"]}
        Article Description: {state["description"]}
        Article Content: {state["body"]}

        {previous_posts_section}

        Style guide (based on how I write):
        - First person, personal tone
        - Conversational and authentic, like talking to a friend
        - Show genuine enthusiasm about the topic
        - Short paragraphs, easy to read
        - Can use 1-2 emojis if it feels natural (This is optional depending on the post tone, is not required in every post)
        - NO hashtags
        - Keep it brief (2-4 sentences max)
        - Do NOT include promotional details like "tech preview", "trial", "free tier", "available now", etc.
        - Focus on the technical content and value, not marketing

        Example of my writing style:
        "One year ago, I began my journey to deepen my knowledge in Elastic, particularly in Elasticsearch. Today, I'm thrilled to share that I am now officially an Elasticsearch Certified Engineer! 🚀"

        Now write a post promoting this article in that same personal, enthusiastic style.
        Return ONLY the post text, nothing else.
    """

    response = llm.invoke(prompt)
    state["post_text"] = response.content
    return state


def build_workflow() -> StateGraph:
    """Build the LangGraph workflow."""
    workflow = StateGraph(PostState)
    workflow.add_node("generate", generate_post)
    workflow.set_entry_point("generate")
    workflow.add_edge("generate", END)
    return workflow.compile()


class PostGenerationError(Exception):
    """Raised when post generation fails."""

    pass


def generate_linkedin_post(
    title: str, description: str, body: str, previous_posts: list[str] | None = None
) -> str:
    """Generate a LinkedIn post for an article.

    Raises:
        PostGenerationError: If generation fails or returns invalid content.
    """
    try:
        workflow = build_workflow()

        result = workflow.invoke(
            {
                "title": title,
                "description": description,
                "body": body,
                "previous_posts": previous_posts or [],
                "post_text": "",
            }
        )

        post_text = result.get("post_text", "")

        # Validate the result
        if not post_text or len(post_text.strip()) < 20:
            raise PostGenerationError("Generated post is empty or too short")

        return post_text

    except PostGenerationError:
        raise
    except Exception as e:
        raise PostGenerationError(f"Failed to generate post: {str(e)}")
