import requests
from bs4 import BeautifulSoup
from langchain.embeddings import HuggingFaceEmbeddings
import os
import json
import subprocess
import sys
sys.path.append('./')
import podcast_downloader.helpers as helpers
from podcast_downloader.helpers import slugify, load_embeddings, update_embeddings
from langchain.vectorstores import FAISS
from langchain.document_loaders import DirectoryLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

DB_FAISS_PATH = 'vectorstore/db_faiss'
DATA_PATH = './podcast_downloader/transcripts'
DESCRIPTIONS_PATH = './podcast_downloader/descriptions_vectorstore/db_faiss'
embeddings = HuggingFaceEmbeddings(model_name='intfloat/multilingual-e5-small',
                                       model_kwargs={'device': 'cpu'})

class Podcast:
    def __init__(self, name, rss_feed_url):
        # Definir atributos de clase
        self.name = name
        self.rss_feed_url = rss_feed_url
        self.embeddings = helpers.get_embeddings_transformer()
        
        # Definir directorios de clase
        base_path = helpers.get_root_dir()
        self.download_directory = f'{base_path}/downloads/{slugify(name)}'
        self.transcription_directory = f'{base_path}/transcripts/{slugify(name)}'

    
        # Crear directorios de clase
        for dir in [self.download_directory, self.transcription_directory]:
            if not os.path.exists(dir):
                os.makedirs(dir)

    def search_items(self, message, **kwargs):
        matched_podcasts = []
        # Obtener los items del podcast
        items = self.get_items()
        # Obtener los embeddings del podcast respecto a sus descripciones
        store_name = slugify(self.name)
        path = helpers.get_desc_emb_dir()
        db_description_embeddings = load_embeddings(store_name, path, self.embeddings, host_documents=False)['faiss_index']
        # Instanciar retriever
        retriever = db_description_embeddings.as_retriever(search_kwargs=kwargs)
        # Obtener descripciones que se asimilen al mensaje
        docs = retriever.get_relevant_documents(message)
        # Obtener los episodios indexados por título
        doc_descriptions = [x.page_content for x in docs]
        items_descriptions = [self.get_cleaned_description(x) for x in items]

        for doc_description in doc_descriptions:
            ind_description = items_descriptions.index(doc_description)
            matched_podcasts += [items[ind_description]]

        return matched_podcasts
    
    def update_description_embeddings(self):
        '''
        Actualizar description_embeddings del podcast con un máximo de items_limit 
        '''
        # Obtener episodios del podcast
        items = self.get_items()
        
        # Obtener los embeddings del podcast respecto a sus descripciones
        store_name = slugify(self.name)
        path = helpers.get_desc_emb_dir()
        metadata = load_embeddings(store_name, path, embeddings, host_documents=False)
        db_descriptions = metadata['texts'] 
    
        for item in items:
            description = self.get_cleaned_description(item)
            if description not in db_descriptions:
                # Agregar description embedding 
                update_embeddings([description],store_name, path, embeddings, host_documents=False)

    # Paragraph embeddings methods    
    def update_paragraph_embeddings(self, title, url):
        slugified_episode = slugify(title)
        transcripts_paths = os.listdir(self.transcription_directory)
        if f'{slugified_episode}.txt' not in transcripts_paths:
            self.generate_transcript(slugified_episode, url)

            db = None

            loader = TextLoader(f'{self.transcription_directory}/{slugified_episode}.txt')
            documents = loader.load()
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=400, chunk_overlap=50)
            docs = text_splitter.split_documents(documents)
            for doc in docs:
                doc.metadata['podcast'] = self.name
                doc.metadata['episode'] = title
            
            if not os.path.exists(DB_FAISS_PATH):
                db = FAISS.from_documents(docs, embeddings)
            else:
                db =  FAISS.load_local(DB_FAISS_PATH, embeddings)
                db.add_documents(docs, embeddings)
                 
            db.save_local(DB_FAISS_PATH)


        # episodes_embeddings_path = helpers.get_dir(slugify(self.name), helpers.get_par_emb_dir())
        # if f'faiss_{slugified_episode}.pkl' not in os.listdir(episodes_embeddings_path):
        #     loader = TextLoader(f'{self.transcription_directory}/{slugified_episode}.txt')
        #     documents = loader.load()
        #     text_splitter = CharacterTextSplitter(chunk_size=400, chunk_overlap=50)
        #     docs = text_splitter.split_documents(documents)
            
        #     load_embeddings(slugified_episode, episodes_embeddings_path, self.embeddings, host_documents=True, docs=docs)

    def generate_transcript(self, episode_path, url):
        base_dir = helpers.get_root_dir()
        download_episode_path = f'{self.download_directory}/{episode_path}.mp3'
        print("Download path: ", download_episode_path)
        episode_metadata_json = {'url': url, 'download_episode_path': download_episode_path}
        with open(f'{base_dir}/podcast_metadata.json', 'w') as f:
            json.dump(episode_metadata_json, f)
        
        # subprocess.run([f'{base_dir}/run_all.sh'])
        subprocess.call(['python', f'{base_dir}/download_podcasts.py'])
        subprocess.call(['python', f'{base_dir}/transcriptions.py'])
        
    # Helpers methods
    def get_items(self):
        page = requests.get(self.rss_feed_url)
        soup = BeautifulSoup(page.text, 'xml')
        return soup.find_all('item')
    
    def get_cleaned_description(self, item):
        raw_description = item.find('description').text
        bs_description = BeautifulSoup(raw_description, 'html.parser')
        description = "\n".join([p.get_text(strip=True) for p in bs_description.find_all('p')])
        return description
    
    
            





        

    
    
    

            
        