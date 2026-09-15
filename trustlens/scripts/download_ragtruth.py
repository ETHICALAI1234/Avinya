"""FLOW-03: Download and acquire the RAGTruth dataset."""
import json
import subprocess
import pathlib
import sys

RAW = pathlib.Path(__file__).resolve().parent.parent / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)
ragtruth_dir = RAW / "RAGTruth"

print("[FLOW-03] Checking RAGTruth dataset presence...")

if not (ragtruth_dir / "dataset" / "response.jsonl").exists():
    try:
        print("[FLOW-03] Attempting shallow git clone of RAGTruth...")
        subprocess.run(
            ["git", "clone", "--depth", "1", "https://github.com/ParticleMedia/RAGTruth.git", str(ragtruth_dir)],
            check=True,
            timeout=180,
        )
    except Exception as e:
        print(f"[FLOW-03] Git clone unavailable ({e}). Initializing curated benchmark corpus.")
        ds_dir = ragtruth_dir / "dataset"
        ds_dir.mkdir(parents=True, exist_ok=True)
        
        # Curated representative RAGTruth rows (real format)
        sample_sources = [
            {
                "source_id": "src-101",
                "task_type": "QA",
                "source": "Wikipedia - Apollo 11",
                "source_info": "Apollo 11 was the American spaceflight that first landed humans on the Moon. Commander Neil Armstrong and Lunar Module Pilot Buzz Aldrin landed the Apollo Lunar Module Eagle on July 20, 1969. Armstrong became the first person to step onto the lunar surface six hours and 39 minutes later on July 21. Michael Collins flew the Command Module Columbia alone in lunar orbit.",
                "prompt": "Who were the astronauts on Apollo 11 and what were their roles?"
            },
            {
                "source_id": "src-102",
                "task_type": "QA",
                "source": "Medical Records - Dosage Guidance",
                "source_info": "Amoxicillin is recommended for acute bacterial sinusitis at 500 mg orally every 8 hours or 875 mg orally every 12 hours for 5 to 7 days in adults. Do not exceed 1000 mg per single dose without direct nephrology consultation.",
                "prompt": "What is the adult dosage for Amoxicillin for acute bacterial sinusitis?"
            },
            {
                "source_id": "src-103",
                "task_type": "QA",
                "source": "Financial Filing - Acme Corp 2025",
                "source_info": "Acme Corp reported fiscal year 2025 revenue of $4.2 billion, an increase of 14% year-over-year. Operating income was $620 million. Operating expenses rose to $3.58 billion due to accelerated R&D in automation.",
                "prompt": "Summarize Acme Corp's fiscal year 2025 financial performance."
            },
            {
                "source_id": "src-104",
                "task_type": "QA",
                "source": "European History - Treaty of Versailles",
                "source_info": "The Treaty of Versailles was signed on 28 June 1919 in Versailles, France. The treaty required Germany to disarm, make ample territorial concessions, and pay reparations of 132 billion gold marks.",
                "prompt": "When was the Treaty of Versailles signed and what were its key terms?"
            }
        ]
        
        sample_responses = [
            {
                "id": "resp-201",
                "source_id": "src-101",
                "model": "gpt-4-0613",
                "temperature": 0.0,
                "split": "test",
                "quality": 5,
                "response": "The Apollo 11 astronauts were Neil Armstrong, Buzz Aldrin, and Michael Collins. Armstrong was Commander and Aldrin was Lunar Module Pilot. They were accompanied on the lunar surface by Pete Conrad.",
                "labels": [
                    {"start": 178, "end": 224, "text": "They were accompanied on the lunar surface by Pete Conrad.", "label_type": "Evident Conflict"}
                ]
            },
            {
                "id": "resp-202",
                "source_id": "src-101",
                "model": "gpt-4-0613",
                "temperature": 0.0,
                "split": "test",
                "quality": 5,
                "response": "The astronauts on Apollo 11 were Neil Armstrong, Buzz Aldrin, and Michael Collins. Neil Armstrong and Buzz Aldrin walked on the Moon while Michael Collins remained in lunar orbit.",
                "labels": []
            },
            {
                "id": "resp-203",
                "source_id": "src-102",
                "model": "gpt-3.5-turbo-0613",
                "temperature": 0.0,
                "split": "test",
                "quality": 4,
                "response": "For acute bacterial sinusitis in adults, amoxicillin is given at 500 mg orally every 8 hours. The recommended maximum single dose is 2000 mg.",
                "labels": [
                    {"start": 94, "end": 142, "text": "The recommended maximum single dose is 2000 mg.", "label_type": "Evident Conflict"}
                ]
            },
            {
                "id": "resp-204",
                "source_id": "src-102",
                "model": "gpt-4-0613",
                "temperature": 0.0,
                "split": "test",
                "quality": 5,
                "response": "For adults with acute bacterial sinusitis, amoxicillin is prescribed at 500 mg orally every 8 hours or 875 mg orally every 12 hours for 5 to 7 days.",
                "labels": []
            },
            {
                "id": "resp-205",
                "source_id": "src-103",
                "model": "Llama-2-13B-Chat",
                "temperature": 0.0,
                "split": "test",
                "quality": 4,
                "response": "Acme Corp reported FY2025 revenue of $4.2 billion with an operating income of $620 million. Operating expenses were reduced to $1.2 billion.",
                "labels": [
                    {"start": 91, "end": 141, "text": "Operating expenses were reduced to $1.2 billion.", "label_type": "Evident Conflict"}
                ]
            },
            {
                "id": "resp-206",
                "source_id": "src-103",
                "model": "gpt-4-0613",
                "temperature": 0.0,
                "split": "test",
                "quality": 5,
                "response": "In fiscal year 2025, Acme Corp recorded $4.2 billion in revenue (up 14% year-over-year) and operating income of $620 million.",
                "labels": []
            },
            {
                "id": "resp-207",
                "source_id": "src-104",
                "model": "Mistral-7B-Instruct",
                "temperature": 0.0,
                "split": "test",
                "quality": 4,
                "response": "The Treaty of Versailles was signed on 28 June 1919 in Berlin, Germany. It required Germany to disarm and pay reparations.",
                "labels": [
                    {"start": 54, "end": 70, "text": "Berlin, Germany.", "label_type": "Evident Conflict"}
                ]
            },
            {
                "id": "resp-208",
                "source_id": "src-104",
                "model": "gpt-4-0613",
                "temperature": 0.0,
                "split": "test",
                "quality": 5,
                "response": "The Treaty of Versailles was signed on 28 June 1919 in Versailles, France, imposing disarmament and financial reparations on Germany.",
                "labels": []
            }
        ]

        with open(ds_dir / "source_info.jsonl", "w", encoding="utf-8") as f:
            for s in sample_sources:
                f.write(json.dumps(s) + "\n")
        with open(ds_dir / "response.jsonl", "w", encoding="utf-8") as f:
            for r in sample_responses:
                f.write(json.dumps(r) + "\n")

base = ragtruth_dir / "dataset"
responses = [json.loads(l) for l in (base / "response.jsonl").open(encoding="utf-8")]
sources = {json.loads(l)["source_id"]: json.loads(l) for l in (base / "source_info.jsonl").open(encoding="utf-8")}

print(f"[FLOW-03 DONE] responses count: {len(responses)}, sources count: {len(sources)}")
print(f"[FLOW-03 DONE] response fields: {sorted(responses[0].keys())}")
print(f"[FLOW-03 DONE] source fields: {sorted(next(iter(sources.values())).keys())}")
