import fitz # PyMuPDF
import re
import os
import json

pdf_path = r"機車駕照筆試題庫(全部804題)-1150218.pdf"
doc = fitz.open(pdf_path)

webapp_pages_dir = r"c:\Users\WS293\OneDrive\桌面\Antigravity\無人機測驗題庫WEBAPP\pages"
os.makedirs(webapp_pages_dir, exist_ok=True)

# 1. Verify/Render PDF page PNGs
print("Verifying PDF page PNGs...")
for page_idx in range(doc.page_count):
    page_img_path = os.path.join(webapp_pages_dir, f"page_{page_idx + 1}.png")
    if not os.path.exists(page_img_path):
        page = doc[page_idx]
        pix = page.get_pixmap(dpi=150)
        pix.save(page_img_path)
print("Page PNGs verified.")

questions = []

# Helper to split options
def split_options_text(text):
    text = text.replace("（", "(").replace("）", ")")
    text = re.sub(r'\(\s*([1-4])\s*\)', r'(\1)', text)
    
    opt1_split = text.split("(1)")
    opt1_text = ""
    opt2_text = ""
    opt3_text = ""
    q_text = ""
    
    if len(opt1_split) >= 2:
        q_text = opt1_split[0].strip()
        rest = opt1_split[1]
        
        opt2_split = rest.split("(2)")
        if len(opt2_split) >= 2:
            opt1_text = opt2_split[0].strip()
            rest2 = opt2_split[1]
            
            opt3_split = rest2.split("(3)")
            if len(opt3_split) >= 2:
                opt2_text = opt3_split[0].strip()
                opt3_text = opt3_split[1].strip()
            else:
                opt2_text = rest2.strip()
        else:
            opt1_text = rest.strip()
    else:
        q_text = text.strip()
        
    return q_text, opt1_text, opt2_text, opt3_text

# Parse page by page
for page_idx in range(doc.page_count):
    page = doc[page_idx]
    
    # Extract blocks to find image block bounds
    page_dict = page.get_text("dict")
    image_blocks = [b for b in page_dict["blocks"] if b["type"] == 1]
    
    words = page.get_text("words")
    cleaned_words = []
    for w in words:
        x0, y0, x1, y1, text, block_no, line_no, word_no = w
        text = text.replace("（", "(").replace("）", ")")
        if y0 >= 50 and y1 <= 790:
            cleaned_words.append({
                "x0": x0, "y0": y0, "x1": x1, "y1": y1,
                "text": text
            })
            
    cleaned_words.sort(key=lambda w: (w["y0"], w["x0"]))
    
    # Identify QIDs on this page using physical location without global strict loop
    page_qids = []
    for w in cleaned_words:
        if 25 <= w["x0"] <= 60:
            text_num = re.sub(r'\D', '', w["text"])
            if text_num and text_num.isdigit():
                val = int(text_num)
                if 1 <= val <= 810:
                    # Deduplicate Y-level overlapping QIDs
                    if not any(abs(item[1]["y0"] - w["y0"]) < 5 for item in page_qids):
                        page_qids.append((val, w))
                        
    page_qids.sort(key=lambda item: item[1]["y0"])
    
    if not page_qids:
        continue
        
    # Process Orphan Options (Cross-page options)
    first_qid_val, first_qid_word = page_qids[0]
    first_qid_y = first_qid_word["y0"]
    
    # Identify physical lines above first_qid_y
    top_lines = []
    col3_words = [w for w in cleaned_words if w["x0"] > 96]
    for qw in col3_words:
        if qw["y1"] < first_qid_y and (first_qid_y - qw["y0"] > 15):
            found = False
            for line in top_lines:
                if abs(qw["y0"] - line["y0"]) < 4:
                    line["words"].append(qw)
                    line["y0"] = min(line["y0"], qw["y0"])
                    line["y1"] = max(line["y1"], qw["y1"])
                    found = True
                    break
            if not found:
                top_lines.append({"y0": qw["y0"], "y1": qw["y1"], "words": [qw]})
    for l in top_lines:
        l["text"] = "".join(qw["text"] for qw in sorted(l["words"], key=lambda qw: qw["x0"]))
    top_lines.sort(key=lambda l: l["y0"])
    
    last_opt_line = None
    for l in reversed(top_lines):
        if any(opt in l["text"] for opt in ["(1)", "(2)", "(3)"]):
            last_opt_line = l
            break
            
    if last_opt_line:
        orphan_limit_y = last_opt_line["y1"]
    else:
        orphan_limit_y = (50 + first_qid_y) / 2
        
    orphan_words = [w for w in cleaned_words if w["y1"] <= orphan_limit_y + 1 and w["x0"] > 96]
    if orphan_words and len(questions) > 0:
        lines_dict = {}
        for qw in orphan_words:
            found_line = None
            for ly in lines_dict.keys():
                if abs(qw["y0"] - ly) < 4:
                    found_line = ly
                    break
            if found_line is not None:
                lines_dict[found_line].append(qw)
            else:
                lines_dict[qw["y0"]] = [qw]
        
        sorted_lines_y = sorted(lines_dict.keys())
        line_texts = []
        for ly in sorted_lines_y:
            line_words = sorted(lines_dict[ly], key=lambda qw: qw["x0"])
            line_str = "".join(qw["text"] for qw in line_words)
            line_texts.append(line_str.strip())
        
        orphan_text = "\n".join(line_texts)
        last_q = questions[-1]
        
        # Scenario A: The whole option block starting with (1) is pushed to the next page
        if "(1)" in orphan_text:
            _, opt1, opt2, opt3 = split_options_text(orphan_text)
            if opt1 and opt2:
                opts = []
                opts.append(f"(A) {opt1}")
                opts.append(f"(B) {opt2}")
                if opt3:
                    opts.append(f"(C) {opt3}")
                
                last_q["options"] = opts
                ans_idx_map = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
                last_q["answerIndex"] = ans_idx_map[last_q["answerLabel"]]
                print(f"Fixed cross-page options (Type A) for Q{last_q['originalId']} using orphan text on page {page_idx+1}")
            else:
                raise ValueError(f"Orphan text parsed invalid option sequence for Q{last_q['originalId']}: {repr(orphan_text)}")
                
        # Scenario B: Option (1) started on previous page, but (2) and (3) are pushed to the next page
        elif "(2)" in orphan_text:
            opt2_split = orphan_text.split("(2)")
            continuation_text = opt2_split[0].strip()
            rest = opt2_split[1]
            opt3_split = rest.split("(3)")
            opt2_text = opt3_split[0].strip()
            opt3_text = opt3_split[1].strip() if len(opt3_split) >= 2 else ""
            
            if len(last_q["options"]) > 0:
                # Merge continuation text to option (A)
                last_q["options"][0] = (last_q["options"][0] + " " + continuation_text).strip()
            
            opts = [last_q["options"][0]]
            if opt2_text:
                opts.append(f"(B) {opt2_text}")
            if opt3_text:
                opts.append(f"(C) {opt3_text}")
                
            last_q["options"] = opts
            ans_idx_map = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
            last_q["answerIndex"] = ans_idx_map[last_q["answerLabel"]]
            print(f"Fixed cross-page options (Type B) for Q{last_q['originalId']} using orphan text on page {page_idx+1}")
            
        # Scenario C: Option (1) and (2) started on previous page, but (3) is pushed to the next page
        elif "(3)" in orphan_text:
            opt3_split = orphan_text.split("(3)")
            continuation_text = opt3_split[0].strip()
            opt3_text = opt3_split[1].strip() if len(opt3_split) >= 2 else ""
            
            if len(last_q["options"]) > 1:
                # Merge continuation text to option (B)
                last_q["options"][1] = (last_q["options"][1] + " " + continuation_text).strip()
            elif len(last_q["options"]) > 0:
                # Fallback to (A)
                last_q["options"][0] = (last_q["options"][0] + " " + continuation_text).strip()
                
            opts = [last_q["options"][0]]
            if len(last_q["options"]) > 1:
                opts.append(last_q["options"][1])
            if opt3_text:
                opts.append(f"(C) {opt3_text}")
                
            last_q["options"] = opts
            ans_idx_map = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
            last_q["answerIndex"] = ans_idx_map[last_q["answerLabel"]]
            print(f"Fixed cross-page options (Type C) for Q{last_q['originalId']} using orphan text on page {page_idx+1}")
            
        # Scenario D: Pure continuation text for the last option without any new tags
        else:
            if len(last_q["options"]) > 0:
                last_q["options"][-1] = (last_q["options"][-1] + " " + orphan_text).strip()
                ans_idx_map = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
                last_q["answerIndex"] = ans_idx_map[last_q["answerLabel"]]
                print(f"Fixed cross-page options (Type D) for Q{last_q['originalId']} using orphan text on page {page_idx+1}")
                    
    # Pre-merge column 3 words into physical lines
    col3_words = [w for w in cleaned_words if w["x0"] > 96]
    physical_lines = []
    for qw in col3_words:
        found = False
        for line in physical_lines:
            if abs(qw["y0"] - line["y0"]) < 4:
                line["words"].append(qw)
                line["y0"] = min(line["y0"], qw["y0"])
                line["y1"] = max(line["y1"], qw["y1"])
                found = True
                break
        if not found:
            physical_lines.append({"y0": qw["y0"], "y1": qw["y1"], "words": [qw]})
            
    for l in physical_lines:
        l["text"] = "".join(qw["text"] for qw in sorted(l["words"], key=lambda qw: qw["x0"]))
        
    physical_lines.sort(key=lambda l: l["y0"])
    
    # Clean up orphan lines that have been processed and merged
    if orphan_words:
        orphan_max_y = max(qw["y1"] for qw in orphan_words)
        physical_lines = [l for l in physical_lines if l["y0"] > orphan_max_y + 1]
    
    # Helper to find adaptive title start Y-coordinate with strict safety firewall
    def find_title_start(idx):
        w_qid = page_qids[idx][1]
        w_qid_y = w_qid["y0"]
        
        # Lower bound safety firewall: must be below the last option (including physical continuations) of the previous question
        if idx == 0:
            min_y = 50
        else:
            prev_y = page_qids[idx - 1][1]["y0"]
            
            # Find all direct option lines between prev_y and w_qid_y with semantic-physical dual validation
            direct_opts = []
            for l in physical_lines:
                if prev_y <= l["y0"] < w_qid_y:
                    if any(opt in l["text"] for opt in ["(1)", "(2)", "(3)"]):
                        dist = abs(l["y0"] - w_qid_y)
                        is_multi_opt = "(1)" in l["text"] and any(opt in l["text"] for opt in ["(2)", "(3)"])
                        if is_multi_opt:
                            if dist > 15:
                                direct_opts.append(l)
                        else:
                            if dist > 35:
                                direct_opts.append(l)
            
            # Propagate option property downward to catch continuation lines (Y distance < 8pt)
            all_prev_opts = []
            if direct_opts:
                sorted_cand = [l for l in physical_lines if prev_y <= l["y0"] < w_qid_y]
                sorted_cand.sort(key=lambda l: l["y0"])
                is_opt = [False] * len(sorted_cand)
                for ic, l_c in enumerate(sorted_cand):
                    if l_c in direct_opts:
                        is_opt[ic] = True
                for ic in range(len(sorted_cand)):
                    if is_opt[ic]:
                        for next_ic in range(ic + 1, len(sorted_cand)):
                            if not is_opt[next_ic]:
                                if sorted_cand[next_ic]["y0"] - sorted_cand[next_ic - 1]["y1"] < 8 and abs(sorted_cand[next_ic]["y0"] - w_qid_y) > 15:
                                    is_opt[next_ic] = True
                                else:
                                    break
                all_prev_opts = [sorted_cand[ic] for ic in range(len(sorted_cand)) if is_opt[ic]]
                
            if all_prev_opts:
                min_y = max(l["y1"] for l in all_prev_opts) + 2
            else:
                min_y = (prev_y + w_qid_y) / 2
                
        max_y = w_qid_y + 15
        
        candidates = []
        for l in physical_lines:
            if min_y <= l["y0"] <= max_y:
                # Exclude lines that are pure option continuations (e.g. contain (2) or (3) but NOT (1))
                has_opt1 = "(1)" in l["text"]
                has_other_opts = any(opt in l["text"] for opt in ["(2)", "(3)"])
                if has_other_opts and not has_opt1:
                    continue
                candidates.append(l["y0"])
                    
        # Include overlapping image blocks as candidates
        for img in image_blocks:
            img_y0 = img["bbox"][1]
            if min_y <= img_y0 <= max_y:
                candidates.append(img_y0)
                
        if candidates:
            return min(candidates)
        return w_qid_y
        
    all_y1s = [w["y1"] for w in cleaned_words] + [b["bbox"][3] for b in image_blocks]
    page_content_bottom = max(all_y1s) if all_y1s else 780
    
    # Parse questions on this page
    for i, (qid, w_qid) in enumerate(page_qids):
        # Adaptive Y-cut based on title start alignment Invariant
        y_top = find_title_start(i) - 3
        
        if i == len(page_qids) - 1:
            y_bottom = min(800, page_content_bottom + 10)
        else:
            y_bottom = find_title_start(i + 1) - 3
            
        # Find Answer in Column 2 (75 <= x0 <= 95)
        ans = None
        for w in cleaned_words:
            if (75 <= w["x0"] <= 95) and (y_top - 2 <= w["y0"] <= y_bottom + 2) and w["text"] in ["1", "2", "3"]:
                if abs(w["y0"] - w_qid["y0"]) < 20:
                    ans = int(w["text"])
                    break
        if ans is None:
            for w in cleaned_words:
                if (75 <= w["x0"] <= 95) and (y_top - 2 <= w["y0"] <= y_bottom + 2) and w["text"] in ["1", "2", "3"]:
                    ans = int(w["text"])
                    break
                    
        # Fail-Fast if answer not found
        if ans is None:
            raise ValueError(f"Fail-Fast: Answer not found for QID {qid} on page {page_idx+1} (Y range: {y_top:.1f} - {y_bottom:.1f})")
            
        # Format Text (collecting words starting from x0 > 96)
        q_words = [w for w in cleaned_words if w["x0"] > 96 and (y_top <= w["y0"] <= y_bottom)]
        
        # Check image blocks overlapping this Y range
        is_image_question = False
        for img in image_blocks:
            img_y0, img_y1 = img["bbox"][1], img["bbox"][3]
            # Check overlap
            if not (y_bottom <= img_y0 or y_top >= img_y1):
                is_image_question = True
                break
                
        # Format Question Words
        lines_dict = {}
        for qw in q_words:
            found_line = None
            for ly in lines_dict.keys():
                if abs(qw["y0"] - ly) < 4:
                    found_line = ly
                    break
            if found_line is not None:
                lines_dict[found_line].append(qw)
            else:
                lines_dict[qw["y0"]] = [qw]
                
        sorted_lines_y = sorted(lines_dict.keys())
        line_texts = []
        for ly in sorted_lines_y:
            line_words = sorted(lines_dict[ly], key=lambda qw: qw["x0"])
            line_str = "".join(qw["text"] for qw in line_words)
            line_texts.append(line_str.strip())
            
        block_text = "\n".join(line_texts)
        q_text, opt1, opt2, opt3 = split_options_text(block_text)
        
        q_text = re.sub(rf'\b{qid}\b', '', q_text)
        q_text = re.sub(rf'\b{ans}\b', '', q_text)
        q_text = re.sub(r'[\s━=]+', ' ', q_text).strip()
        
        # Fail-Fast: if question text is missing but no image block is detected
        if (not q_text or len(q_text) < 4) and not is_image_question:
            if not q_text:
                raise ValueError(f"Fail-Fast: Missing question text for QID {qid} on page {page_idx+1} but no PDF image block overlaps!")
            
        if is_image_question and (not q_text or len(q_text) < 4):
            q_text = f"[圖表/號誌題] 請看下圖回答第 {qid} 題"
            
        opt1_text = re.sub(r'\s+', ' ', opt1).strip()
        opt2_text = re.sub(r'\s+', ' ', opt2).strip()
        opt3_text = re.sub(r'\s+', ' ', opt3).strip()
        
        opts = []
        if opt1_text: opts.append(f"(A) {opt1_text}")
        if opt2_text: opts.append(f"(B) {opt2_text}")
        if opt3_text: opts.append(f"(C) {opt3_text}")
        
        if not opts:
            opts = ["(A) 是", "(B) 否"]
            
        # Map answerIndex and label
        ans_chars = ['A', 'B', 'C', 'D']
        ans_char = ans_chars[ans - 1]
        ans_idx = ans - 1
        
        # Determine chapter
        chapter_keywords = {
            "正確觀念與態度": 1,
            "主動停讓文化": 2,
            "安全駕駛能力": 3,
            "事故預防及處理": 4,
            "禁止不當行為": 5,
            "行車檢查": 6,
            "平交道、強制險、環保駕駛、特殊天候": 7,
        }
        
        chapter_name = "正確觀念與態度"
        chapter_id = 1
        page_text = page.get_text()
        for kw, cid in chapter_keywords.items():
            if kw in page_text:
                chapter_name = kw
                chapter_id = cid
                break
                
        questions.append({
            "id": len(questions) + 1,
            "originalId": qid,
            "question": q_text,
            "options": opts,
            "answerIndex": ans_idx,
            "answerLabel": ans_char,
            "answer": ans_char, # backward compatibility
            "chapter": chapter_id,
            "chapter_name": chapter_name,
            "page": page_idx + 1,
            "crop_x": 0,
            "crop_y": int(y_top),
            "crop_width": 595.32,
            "crop_height": int(y_bottom - y_top),
            "y_top": int(y_top),
            "y_bottom": int(y_bottom),
            "page_width": 595.32,
            "page_height": 841.92,
            "is_image_question": is_image_question
        })

# Post-processing: Deduplicate and sort
questions.sort(key=lambda q: q["originalId"])

cleaned_questions = []
seen_qids = {}
for q in questions:
    orig_id = q["originalId"]
    if orig_id in seen_qids:
        existing = seen_qids[orig_id]
        if len(q["options"]) > len(existing["options"]):
            seen_qids[orig_id] = q
        elif len(q["options"]) == len(existing["options"]) and not q["is_image_question"] and existing["is_image_question"]:
            seen_qids[orig_id] = q
    else:
        seen_qids[orig_id] = q

cleaned_questions = sorted(seen_qids.values(), key=lambda q: q["originalId"])

# Re-assign sequential ids
for idx, q in enumerate(cleaned_questions):
    q["id"] = idx + 1

# 4. Strict Validation check (Fail-Fast)
print("\n--- Starting Post-processing Validation ---")

# Exact 806 count
if len(cleaned_questions) != 806:
    raise ValueError(f"Validation Error: Total unique questions is {len(cleaned_questions)}, expected exactly 806!")

# Sequential and unique ids
for idx, q in enumerate(cleaned_questions):
    expected_id = idx + 1
    if q["id"] != expected_id or q["originalId"] != expected_id:
        raise ValueError(f"Validation Error: Question ID sequence mismatch! Index {idx+1} has originalId {q['originalId']}")

# Option range and answer validity
for q in cleaned_questions:
    if not (0 <= q["answerIndex"] < len(q["options"])):
        raise ValueError(f"Validation Error: Q{q['id']} answerIndex {q['answerIndex']} is out of range for options: {q['options']}")
    
    # Verification of physical crop boxes for image questions
    if q["is_image_question"]:
        img_file = os.path.join(webapp_pages_dir, f"page_{q['page']}.png")
        if not os.path.exists(img_file):
            raise ValueError(f"Validation Error: Image asset missing: {img_file}")
            
        # Invariant checks
        if q["crop_x"] != 0 or q["crop_width"] != 595.32:
            raise ValueError(f"Validation Error: Q{q['id']} fails full-width invariant (crop_x={q['crop_x']}, crop_width={q['crop_width']})")
            
        if not (0 <= q["crop_y"] < 841.92):
            raise ValueError(f"Validation Error: Q{q['id']} crop_y {q['crop_y']} out of page height bounds!")
            
        if q["crop_height"] <= 0:
            raise ValueError(f"Validation Error: Q{q['id']} crop_height is invalid: {q['crop_height']}")
            
        if q["crop_y"] + q["crop_height"] > 841.92:
            raise ValueError(f"Validation Error: Q{q['id']} crop bounding box exceeds page limits (y={q['crop_y']}, height={q['crop_height']})")

print("All validations PASSED successfully!")

# Save database
output_json_path = r"c:\Users\WS293\OneDrive\桌面\Antigravity\無人機測驗題庫WEBAPP\motorcycle_quiz_data.json"
with open(output_json_path, "w", encoding="utf-8") as f:
    json.dump(cleaned_questions, f, ensure_ascii=False, indent=2)
print("Saved motorcycle quiz data to JSON!")
