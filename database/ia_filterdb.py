# Don't Remove Credit @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ
# Ask Doubt on telegram @KingVJ01

import re, base64, json
from struct import pack
from difflib import SequenceMatcher
from pyrogram.file_id import FileId
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from info import FILE_DB_URI, SEC_FILE_DB_URI, DATABASE_NAME, COLLECTION_NAME, MULTIPLE_DATABASE, USE_CAPTION_FILTER, MAX_B_TN

# First Database For File Saving 
client = MongoClient(FILE_DB_URI)
db = client[DATABASE_NAME]
col = db[COLLECTION_NAME]

# Second Database For File Saving
sec_client = MongoClient(SEC_FILE_DB_URI)
sec_db = sec_client[DATABASE_NAME]
sec_col = sec_db[COLLECTION_NAME]


async def save_file(media):
    """Save file in the database."""
    
    file_id = unpack_new_file_id(media.file_id)
    file_name = clean_file_name(media.file_name)
    
    file = {
        'file_id': file_id,
        'file_name': file_name,
        'file_size': media.file_size,
        'caption': media.caption.html if media.caption else None
    }

    if is_file_already_saved(file_id, file_name):
        return False, 0

    try:
        col.insert_one(file)
        print(f"{file_name} is successfully saved.")
        return True, 1
    except DuplicateKeyError:
        print(f"{file_name} is already saved.")
        return False, 0
    except:
        if MULTIPLE_DATABASE:
            try:
                sec_col.insert_one(file)
                print(f"{file_name} is successfully saved.")
                return True, 1
            except DuplicateKeyError:
                print(f"{file_name} is already saved.")
                return False, 0
        else:
            print("Your Current File Database Is Full, Turn On Multiple Database Feature And Add Second File Mongodb To Save File.")

def clean_file_name(file_name):
    """Clean and format the file name."""
    file_name = re.sub(r"(_|\-|\.|\+)", " ", str(file_name)) 
    unwanted_chars = ['[', ']', '(', ')', '{', '}']
    
    for char in unwanted_chars:
        file_name = file_name.replace(char, '')
        
    return ' '.join(filter(lambda x: not x.startswith('@') and not x.startswith('http') and not x.startswith('www.') and not x.startswith('t.me'), file_name.split()))

def is_file_already_saved(file_id, file_name):
    """Check if the file is already saved in either collection."""
    found1 = {'file_name': file_name}
    found = {'file_id': file_id}

    for collection in [col, sec_col]:
        if collection.find_one(found1) or collection.find_one(found):
            print(f"{file_name} is already saved.")
            return True
            
    return False

async def get_search_results(chat_id, query, file_type=None, max_results=10, offset=0, filter=False):
    """For given query return (results, next_offset)"""
    
    query = query.strip()
    if not query:
        raw_pattern = '.'
    elif ' ' not in query:
        raw_pattern = r'(\b|[\.\+\-_])' + query + r'(\b|[\.\+\-_])'
    else:
        raw_pattern = query.replace(' ', r'.*[\s\.\+\-_]') 
    try:
        regex = re.compile(raw_pattern, flags=re.IGNORECASE)
    except:
        regex = query
    filter = {'file_name': regex}
    files = []
    if MULTIPLE_DATABASE:
        cursor1 = col.find(filter).sort('$natural', -1).skip(offset).limit(max_results)
        cursor2 = sec_col.find(filter).sort('$natural', -1).skip(offset).limit(max_results)
        
        for file in cursor1:
            files.append(file)
        for file in cursor2:
            files.append(file)
    else:
        cursor = col.find(filter).sort('$natural', -1).skip(offset).limit(max_results)
        
        for file in cursor:
            files.append(file)

    total_results = col.count_documents(filter) if not MULTIPLE_DATABASE else (col.count_documents(filter) + sec_col.count_documents(filter))
    next_offset = "" if (offset + max_results) >= total_results else (offset + max_results)

    return files, next_offset, total_results

def _normalize_for_fuzzy(text):
    """Lowercase and strip separators/punctuation so typo comparisons ignore formatting differences."""
    text = re.sub(r"(_|\-|\.|\+)", " ", str(text)).lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

async def get_fuzzy_search_results(chat_id, query, max_results=10, offset=0, min_score=0.5):
    """
    Fallback for misspelled queries: when an exact/substring search finds nothing,
    look for files whose name is CLOSE to the query (minor typos, swapped letters,
    missing/extra characters) instead of requiring an exact spelling match.
    Returns (files, next_offset, total_results) in the same shape as get_search_results.
    """
    query_norm = _normalize_for_fuzzy(query)
    if not query_norm:
        return [], "", 0

    words = [w for w in query_norm.split() if len(w) > 2]
    if not words:
        words = query_norm.split()
    if not words:
        return [], "", 0

    # Narrow candidates to files that contain at least one of the query's words,
    # so we're not scoring the entire collection for every search.
    or_clauses = [re.compile(re.escape(w), flags=re.IGNORECASE) for w in words]
    candidate_filter = {'file_name': {'$in': or_clauses}}

    candidates = []
    seen_ids = set()
    for collection in ([col, sec_col] if MULTIPLE_DATABASE else [col]):
        cursor = collection.find(candidate_filter).sort('$natural', -1).limit(300)
        for file in cursor:
            fid = file.get('file_id')
            if fid in seen_ids:
                continue
            seen_ids.add(fid)
            candidates.append(file)

    if not candidates:
        return [], "", 0

    scored = []
    for file in candidates:
        name_norm = _normalize_for_fuzzy(file.get('file_name', ''))
        ratio = SequenceMatcher(None, query_norm, name_norm).ratio()
        word_hits = sum(1 for w in words if w in name_norm)
        word_score = word_hits / len(words)
        combined = (ratio * 0.4) + (word_score * 0.6)
        if combined >= min_score:
            scored.append((combined, file))

    if not scored:
        return [], "", 0

    scored.sort(key=lambda x: x[0], reverse=True)
    matched_files = [file for _, file in scored]

    total_results = len(matched_files)
    page = matched_files[offset:offset + max_results]
    next_offset = "" if (offset + max_results) >= total_results else (offset + max_results)

    return page, next_offset, total_results

async def get_bad_files(query, file_type=None, use_filter=False):
    """For given query return (results, next_offset)"""
    query = query.strip()
    
    if not query:
        raw_pattern = '.'
    elif ' ' not in query:
        raw_pattern = rf'(\b|[.+-_]){query}(\b|[.+-_])'
    else:
        raw_pattern = query.replace(' ', r'.*[s.+-_]')
    
    try:
        regex = re.compile(raw_pattern, flags=re.IGNORECASE)
    except re.error:
        return [], 0

    filter_criteria = {'file_name': regex}
    if USE_CAPTION_FILTER:
        filter_criteria = {'$or': [filter_criteria, {'caption': regex}]}

    def count_documents(collection):
        return collection.count_documents(filter_criteria)

    total_results = (count_documents(col) + count_documents(sec_col) if MULTIPLE_DATABASE else count_documents(col))

    def find_documents(collection):
        return list(collection.find(filter_criteria))

    files = (find_documents(col) + find_documents(sec_col) if MULTIPLE_DATABASE else find_documents(col))

    return files, total_results

async def get_file_details(query):
    return col.find_one({'file_id': query}) or sec_col.find_one({'file_id': query})

def encode_file_id(s: bytes) -> str:
    r = b""
    n = 0
    for i in s + bytes([22]) + bytes([4]):
        if i == 0:
            n += 1
        else:
            if n:
                r += b"\x00" + bytes([n])
                n = 0
            r += bytes([i])
    return base64.urlsafe_b64encode(r).decode().rstrip("=")
    
def unpack_new_file_id(new_file_id):
    """Return file_id"""
    decoded = FileId.decode(new_file_id)
    file_id = encode_file_id(
        pack(
            "<iiqq",
            int(decoded.file_type),
            decoded.dc_id,
            decoded.media_id,
            decoded.access_hash
        )
    )
    return file_id
    
