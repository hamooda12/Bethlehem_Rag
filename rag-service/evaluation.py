"""IEEE Academic Advisor RAG evaluation: run from rag-service directory.
Requires existing retrieval.py, generation.py and indexed documents.
Writes evaluation_results.json; automated checks are diagnostic, not faithfulness proof.
"""
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from retrieval import retrieve
from generation import answer_question

# Source filename identifiers. Adjust if you renamed the documents.
BIRZEIT = 'أنظمة وتعليمات'
AAUP = 'الأمريكية'

CASES = [
    {'id':'Q01','type':'direct','question':'في جامعة بيرزيت، ما الحد الأقصى للساعات في الفصل الدراسي العادي؟','gold_answer':'18 ساعة عادةً، مع استثناءات تصل إلى 19 أو 21 وفق الشروط.','gold_sources':[BIRZEIT],'evidence':['18 ساعة','19 ساعة','21 ساعة']},
    {'id':'Q02','type':'direct','question':'في جامعة بيرزيت، كيف يُصنّف طالب أنهى 65 ساعة بنجاح؟','gold_answer':'مستوى سنة ثالثة (60–89 ساعة).','gold_sources':[BIRZEIT],'evidence':['60','89']},
    {'id':'Q03','type':'direct','question':'ما الحد الأدنى للمعدل التراكمي للتخرج من جامعة بيرزيت؟','gold_answer':'2.00.','gold_sources':[BIRZEIT],'evidence':['2.00']},
    {'id':'Q04','type':'direct','question':'ما الحد الأقصى للساعات في الدورة الصيفية لطلبة بيرزيت؟','gold_answer':'12 ساعة معتمدة.','gold_sources':[BIRZEIT],'evidence':['الدورة الصيفية','12 ساعة']},
    {'id':'Q05','type':'direct','question':'هل تطرح الجامعة العربية الأمريكية تخصص الأمن السيبراني؟','gold_answer':'نعم، مدرج في دليل برامج 2024/2025 في حرم رام الله.','gold_sources':[AAUP],'evidence':['الأمن السيبراني']},
    {'id':'Q06','type':'paraphrase','question':'إذا معدلي التراكمي في بيرزيت نزل عن 2، شو ممكن يصير؟','gold_answer':'قد يفرض تحذير أكاديمي، مع شروط تتعلق بالساعات واستثناءات في المادة 11.','gold_sources':[BIRZEIT],'evidence':['التحذير الأكاديمي','2.00']},
    {'id':'Q07','type':'paraphrase','question':'في بيرزيت، إذا بدي أسحب مادة بعد التعديل، هل بتأثر على معدلي؟','gold_answer':'الانسحاب الرسمي خلال المدة المسموحة يظهر W ولا يدخل المعدل؛ WF يدخل كرسوب.','gold_sources':[BIRZEIT],'evidence':['منسحب','W']},
    {'id':'Q08','type':'paraphrase','question':'مين بيقوم بإرشاد الطالب المتخصص في جامعة بيرزيت؟','gold_answer':'رئيس الدائرة أو عضو هيئة أكاديمية مكلف بالإرشاد.','gold_sources':[BIRZEIT],'evidence':['رؤساء دوائرهم']},
    {'id':'Q09','type':'multi_document','question':'اذكر تخصصاً في دليل الجامعة العربية الأمريكية، ثم اذكر الحد الأدنى للمعدل التراكمي للتخرج حسب لوائح جامعة بيرزيت. وضّح أن الجامعتين مختلفتان.','gold_answer':'مثلاً الأمن السيبراني من AAUP؛ ومعدل التخرج 2.00 في بيرزيت، ولا تُطبّق لائحة بيرزيت على AAUP.','gold_sources':[BIRZEIT,AAUP],'evidence':['الأمن السيبراني','2.00']},
    {'id':'Q10','type':'unanswerable','question':'كم رسوم الساعة المعتمدة لتخصص الأمن السيبراني في الجامعة العربية الأمريكية للعام 2026؟','gold_answer':'غير مذكورة في الوثائق المرفقة؛ يجب الامتناع.','gold_sources':[],'evidence':[]},
    {'id':'Q11','type':'unanswerable','question':'ما هو رقم الهاتف الشخصي لرئيس قسم التسجيل الحالي في جامعة بيرزيت؟','gold_answer':'غير مذكور في الوثائق المرفقة؛ يجب الامتناع.','gold_sources':[],'evidence':[]},
    {'id':'Q12','type':'misleading','question':'هل صحيح أن طالب الجامعة العربية الأمريكية تحت التحذير الأكاديمي مسموح له 9 إلى 13 ساعة بحسب دليلها المرفق؟','gold_answer':'لا يمكن تأكيد ذلك من دليل AAUP؛ قاعدة 9–13 واردة في لائحة جامعة بيرزيت، لا AAUP.','gold_sources':[BIRZEIT,AAUP],'evidence':['9 ساعات','13 ساعة']},
]


def has_source(filename, expected):
    return unicodedata.normalize("NFC", expected) in unicodedata.normalize("NFC", filename)


def run():
    from ingestion import collection
    filenames = sorted({m['filename'] for m in collection.get(include=['metadatas'])['metadatas']})
    print('Indexed documents:', filenames)
    for label in (BIRZEIT, AAUP):
        if not any(has_source(f, label) for f in filenames):
            raise SystemExit(f'Missing document matching {label!r}; upload both documents or update source identifiers.')

    results = []
    for case in CASES:
        print(f"Running {case['id']} ({case['type']}) ...", flush=True)
        try:
            chunks = retrieve(case['question'], top_k=4)
            response = answer_question(case['question'], top_k=4)
            retrieved_sources = [c['source'] for c in chunks]
            expected = case['gold_sources']
            # Source coverage is a diagnostic; it does NOT prove chunk-level relevance.
            source_hit = all(any(has_source(name, label) for name in retrieved_sources) for label in expected) if expected else None
            cited_sources = response.get('sources', [])
            answer = response.get('answer', '')
            cited_tokens = set(re.findall(r'\[S\d+\]', answer))
            citation_format_pass = (all(f"[{s['citation_id']}]" in cited_tokens for s in cited_sources)
                                    and cited_tokens == {f"[{s['citation_id']}]" for s in cited_sources})
            # Must separately inspect whether claims are actually supported by excerpts.
            abstain_pass = (not response.get('grounded') and not cited_sources) if not expected else None
            row = {
                'id':case['id'], 'type':case['type'], 'question':case['question'],
                'gold_answer':case['gold_answer'], 'gold_sources':expected,
                'actual_answer':answer,
                'retrieved_chunks':chunks,
                'retrieval_source_coverage':source_hit,
                'retrieval_pass':None,  # Manually judge exact evidence relevance.
                'faithfulness_pass':None, # Manually verify every claim using sources.
                'citation_format_pass':citation_format_pass,
                'citation_accuracy_pass':None, # Manually check claim and attribution.
                'abstention_pass':abstain_pass,
                'notes':''
            }
            results.append(row)
        except Exception as exc:
            results.append({'id':case['id'],'question':case['question'],'error':f'{type(exc).__name__}: {exc}'})

    valid_source_checks = [r['retrieval_source_coverage'] for r in results if r.get('retrieval_source_coverage') is not None]
    abstentions = [r['abstention_pass'] for r in results if r.get('abstention_pass') is not None]
    report = {
        'generated_at_utc':datetime.now(timezone.utc).isoformat(),
        'notes':'Source coverage is not Precision@k. Faithfulness and citation accuracy require evidence-based manual review.',
        'diagnostics':{
            'source_coverage_at_4':sum(valid_source_checks)/len(valid_source_checks) if valid_source_checks else None,
            'unanswerable_abstention_rate':sum(abstentions)/len(abstentions) if abstentions else None,
            'completed_cases':sum('error' not in x for x in results),
            'total_cases':len(CASES)
        },
        'results':results
    }
    Path('evaluation_results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('\nDiagnostics:', report['diagnostics'])
    print('Saved evaluation_results.json. Review retrieval_pass, faithfulness_pass, citation_accuracy_pass manually.')

if __name__ == '__main__':
    run()
