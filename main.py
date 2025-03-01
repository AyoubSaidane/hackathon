from connector.connector import GoogleDriveConnector
from rag.parser import Parser
from rag.indexer import Indexer
from llama_index.llms.gemini import Gemini
from rag.retriever import RouterQueryWorkflow
from llama_index.core.query_engine import RetrieverQueryEngine
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import nest_asyncio

# Apply nest_asyncio to allow nested async event loops
nest_asyncio.apply()

class Query(BaseModel):
    message: str
counter = 0  
print(counter)
app = FastAPI(title="CtrlF API")
@app.get("/connect", status_code=200)
async def connection_endpoint():
    global counter
    counter = 0
    try:
        # connect to Google Drive and parse files
        connector = GoogleDriveConnector(['pdf', 'pptx', 'docx'])
        files = connector.list_files()
        parser = Parser()
        global all_data
        all_data = []
        for file in files:
            data = connector.get_file(files, file)
            file_chunks = parser.parse_bytes_io(data)
            all_data.extend(file_chunks)
        global index
        indexer = Indexer()
        index = indexer.index_document(all_data)
        if not files:
            return {"message": "No files found."}
        else:
            return {"message": "Successfully connected to Google Drive."}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

  
@app.post("/query", status_code=200)
async def query_endpoint(query: Query):
    try:

        # retrieve the index and run the query
        global counter
        global index
        if counter == 0:
            indexer = Indexer()
            index = indexer.retrieve_index()

        
            llm = Gemini(model = "models/gemini-2.0-flash")

            doc_retriever = index.as_retriever(
                retrieval_mode="files_via_content", 
                files_top_k=5,
            )
            query_engine_doc = RetrieverQueryEngine.from_args(
                doc_retriever, 
                llm=llm, 
                response_mode="tree_summarize",
            )

            chunk_retriever = index.as_retriever(
                retrieval_mode="chunks", 
                rerank_top_n=10,
            )
            query_engine_chunk = RetrieverQueryEngine.from_args(
                chunk_retriever, 
                llm=llm, 
                response_mode="tree_summarize"
            )
            global router_query_workflow
            router_query_workflow = RouterQueryWorkflow(
                query_engines=[query_engine_doc, query_engine_chunk],
                verbose=True,
                llm=llm,
                timeout=60
            )
            counter += 1
        rag_response = await router_query_workflow.run(query_str=query.message)
        return {"message": rag_response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="localhost", port=8000, reload=True)