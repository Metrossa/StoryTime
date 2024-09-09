import pdfplumber
import openai
import os
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pydub import AudioSegment
from cartesia import Cartesia
import io
from dotenv import load_dotenv
load_dotenv()
openai.api_key = os.getenv('OPENAI_API_KEY')
cartesia = Cartesia(api_key=os.getenv('CARTESIA_API_KEY'))
def extract_text_from_pdf(file_path):
    text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    return text

def chunk_text(text, max_length=4000):
    paragraphs = text.split('\n')
    chunks = []
    current_chunk = ""
    
    for paragraph in paragraphs:
        if len(current_chunk) + len(paragraph) + 1 <= max_length:
            current_chunk += paragraph + "\n"
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = paragraph + "\n"
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks

def preprocess_with_gpt4(chunk):
    try:
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an AI assistant that labels text for an audiobook narrator. Label each paragraph or dialogue as 'MAN', 'WOMAN', or 'NARRATOR'. Output should be in JSON format with the text as the key and the label as the value."},
                {"role": "user", "content": f"Label the following text:\n\n{chunk}"}
            ],
            temperature=0.3,
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"Error processing chunk: {e}")
        return None

def process_chunk(chunk, chunk_index, output_path_prefix):
    labeled_chunk = preprocess_with_gpt4(chunk)
    if labeled_chunk:
        audio_parts = []
        for text, label in labeled_chunk.items():
            voice = "alloy" if label == "NARRATOR" else "nova" if label == "WOMAN" else "echo"
            audio_content = pdf_to_audio(text, voice)
            if audio_content:
                audio_parts.append(audio_content)
        
        if audio_parts:
            output_path = f"{output_path_prefix}_{chunk_index}.mp3"
            with open(output_path, "wb") as out:
                for part in audio_parts:
                    out.write(part)
            print(f'Audio content written to "{output_path}"')
            return output_path
    return None

def pdf_to_audio(pdf_path, output_path_prefix):
    text = extract_text_from_pdf(pdf_path)
    chunks = chunk_text(text)
    
    completed_files = []
    
    for i, chunk in enumerate(chunks):
        output_file = f"{output_path_prefix}_{i}.wav"
        
        # Use Cartesia API to generate audio
        voice_id = "a0e99841-438c-4a64-b679-ae501e7d6091"  # Example voice ID, you can change this
        model_id = "sonic-english"  # Example model ID, you can change this
        
        output_format = {
            "container": "raw",
            "encoding": "pcm_s16le",
            "sample_rate": 44100,
        }
        
        try:
            audio_data = io.BytesIO()
            for output in cartesia.tts.sse(
                model_id=model_id,
                transcript=chunk,
                voice_id=voice_id,
                stream=True,
                output_format=output_format,
            ):
                audio_data.write(output["audio"])
            
            audio_data.seek(0)
            raw_audio = AudioSegment(
                audio_data.getvalue(),
                sample_width=2,
                frame_rate=44100,
                channels=1
            )
            raw_audio.export(output_file, format="wav")
            
            completed_files.append(output_file)
            print(f"Generated audio file: {output_file}")
        except Exception as e:
            print(f"Error generating audio for chunk {i}: {str(e)}")
    
    return completed_files, chunks