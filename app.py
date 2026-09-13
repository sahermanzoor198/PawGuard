"""NutriNest hackathon MVP. Run: streamlit run app.py

Optional .streamlit/secrets.toml (NEVER commit this file):
GROQ_API_KEY = "your-key"
GROQ_MODEL = "openai/gpt-oss-20b"

Python 3.11+. Session-only storage; export a backup before closing.
Nutrition values are illustrative ingredient estimates, not clinical advice.
"""
import json
import math
import os
from datetime import date, timedelta

import pandas as pd
import streamlit as st
from scipy.optimize import lsq_linear

# Per 100 g edible ingredient: kcal, protein, carbohydrate, fat.
# Representative demo values; actual brands/recipes vary. Validate before real use.
# Reference for replacing/curating ingredient records: https://fdc.nal.usda.gov/
ING = {
    'atta': (340, 13, 72, 2.5), 'rice_dry': (365, 7, 80, .7),
    'oats': (379, 13, 68, 6.5), 'lentils_dry': (352, 25, 60, 1.1),
    'chickpeas_cooked': (164, 8.9, 27.4, 2.6), 'kidney_beans_cooked': (127, 8.7, 22.8, .5),
    'chicken_raw': (120, 22.5, 0, 2.6), 'fish_raw': (96, 20, 0, 1.7),
    'egg': (143, 12.6, .7, 9.5), 'milk': (61, 3.2, 4.8, 3.3),
    'yogurt': (61, 3.5, 4.7, 3.3), 'oil': (884, 0, 0, 100),
    'onion': (40, 1.1, 9.3, .1), 'tomato': (18, .9, 3.9, .2),
    'spinach': (23, 2.9, 3.6, .4), 'potato': (77, 2, 17, .1),
    'peas': (81, 5.4, 14.5, .4), 'carrot': (41, .9, 9.6, .2),
    'cucumber': (15, .7, 3.6, .1), 'banana': (89, 1.1, 22.8, .3),
    'apple': (52, .3, 13.8, .2), 'orange': (47, .9, 11.8, .1),
    'peanuts': (567, 25.8, 16.1, 49.2), 'almonds': (579, 21.2, 21.6, 49.9),
}
ALLERGEN = {'atta': 'Wheat', 'oats': 'Oats', 'egg': 'Egg', 'milk': 'Milk',
            'yogurt': 'Milk', 'fish_raw': 'Fish', 'peanuts': 'Peanut', 'almonds': 'Tree nuts'}
ANIMAL = {'chicken_raw', 'fish_raw', 'egg', 'milk', 'yogurt'}
# recipe id, display name, meal slot, finished edible grams, raw/drained ingredients grams
ROWS = [
 ('roti','Plain roti','main',65,{'atta':40}),
 ('rice','Plain rice','main',180,{'rice_dry':60}),
 ('dal','Masoor dal','main',230,{'lentils_dry':55,'tomato':40,'onion':25,'oil':5}),
 ('chana','Chana masala','main',240,{'chickpeas_cooked':160,'tomato':50,'onion':30,'oil':5}),
 ('rajma','Rajma','main',240,{'kidney_beans_cooked':170,'tomato':40,'onion':30,'oil':5}),
 ('chicken','Chicken salan','main',210,{'chicken_raw':140,'tomato':60,'onion':35,'oil':7}),
 ('fish','Pan-cooked fish','main',140,{'fish_raw':170,'oil':5}),
 ('palak','Palak','main',180,{'spinach':230,'onion':30,'oil':5}),
 ('aloo','Aloo matar','main',240,{'potato':140,'peas':80,'tomato':40,'oil':5}),
 ('pulao','Vegetable pulao','main',280,{'rice_dry':60,'peas':50,'carrot':50,'onion':25,'oil':5}),
 ('khichri','Dal khichri','main',300,{'rice_dry':40,'lentils_dry':40,'carrot':40,'oil':4}),
 ('raita','Cucumber raita','side',180,{'yogurt':140,'cucumber':40}),
 ('salad','Kachumber salad','side',180,{'tomato':70,'cucumber':80,'onion':30}),
 ('oatmeal','Milk oats','breakfast',260,{'oats':45,'milk':200}),
 ('oats_water','Water-cooked oats','breakfast',230,{'oats':55}),
 ('omelette','Masala omelette','breakfast',145,{'egg':100,'tomato':25,'onion':20,'oil':4}),
 ('eggs','Boiled eggs','breakfast',100,{'egg':100}),
 ('chana_breakfast','Breakfast chana','breakfast',200,{'chickpeas_cooked':160,'tomato':30,'oil':4}),
 ('roti_breakfast','Breakfast roti','breakfast',65,{'atta':40}),
 ('banana','Banana','snack',120,{'banana':120}),
 ('apple','Apple','snack',150,{'apple':150}),
 ('orange','Orange','snack',150,{'orange':150}),
 ('yogurt','Plain yogurt','snack',170,{'yogurt':170}),
 ('peanuts','Peanuts','snack',25,{'peanuts':25}),
 ('almonds','Almonds','snack',25,{'almonds':25}),
 ('chana_snack','Chana chaat','snack',180,{'chickpeas_cooked':130,'tomato':30,'onion':20}),
]
FOODS = {r[0]:dict(name=r[1],slot=r[2],grams=r[3],ingredients=r[4]) for r in ROWS}
MEALS = ['Breakfast','Lunch','Dinner','Snack']
ACTIVITY = {'Low':1.2,'Light':1.375,'Moderate':1.55,'High':1.725}
GOALS = ['Maintain','Weight loss','Muscle gain']

def nutrition(fid):
    return [sum(ING[k][i]*g/100 for k,g in FOODS[fid]['ingredients'].items()) for i in range(4)]

def targets(p):
    bmr = 10*p['weight'] + 6.25*p['height'] - 5*p['age'] + (5 if p['sex']=='Male' else -161)
    tdee = bmr*ACTIVITY[p['activity']]
    kcal = tdee*({'Maintain':1,'Weight loss':.9,'Muscle gain':1.05}[p['goal']])
    if not 1500 <= kcal <= 3500:
        raise ValueError('Estimated energy needs fall outside this demo range. Seek personalized professional targets.')
    return dict(bmi=round(p['weight']/(p['height']/100)**2,1),bmr=round(bmr),
                kcal=round(kcal),protein=round(kcal*.20/4),carbs=round(kcal*.50/4),fat=round(kcal*.30/9))

def validate_profile(p):
    if not isinstance(p,dict) or not isinstance(p.get('name'),str) or not p['name'].strip() or len(p['name'])>50:
        raise ValueError('Invalid member name.')
    for key,low,high in [('age',20,75),('height',130,220),('weight',40,180)]:
        v=p.get(key)
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not low<=v<=high:
            raise ValueError('Invalid '+key)
    for key,choices in [('sex',['Male','Female']),('activity',ACTIVITY),('goal',GOALS),
                        ('diet',['Non-vegetarian','Vegetarian','Vegan'])]:
        if p.get(key) not in choices: raise ValueError('Invalid '+key)
    if not isinstance(p.get('allergies'),list) or any(a not in set(ALLERGEN.values()) for a in p['allergies']):
        raise ValueError('Unsupported allergy. This demo cannot verify unlisted allergens.')
    if not isinstance(p.get('exclude'),list) or any(k not in ING for k in p['exclude']): raise ValueError('Invalid ingredient exclusions.')
    targets(p)
    return p

def allowed(fid,family):
    ingredients=set(FOODS[fid]['ingredients'])
    allergens={ALLERGEN[k] for k in ingredients if k in ALLERGEN}
    for p in family:
        if allergens & set(p['allergies']) or ingredients & set(p['exclude']): return False
        if p['diet']=='Vegan' and ingredients & ANIMAL: return False
        if p['diet']=='Vegetarian' and ingredients & {'chicken_raw','fish_raw'}: return False
    return True

def pool(family,slot):
    return [k for k,v in FOODS.items() if v['slot']==slot and allowed(k,family)]

def validate_plan(plan,family):
    if not isinstance(plan,list) or len(plan)!=7: raise ValueError('Plan must contain seven days.')
    for d in plan:
        if not isinstance(d,dict) or set(d)!=set(MEALS): raise ValueError('Each day needs four meals.')
        for meal,ids in d.items():
            if not isinstance(ids,list) or not 1<=len(ids)<=4 or len(set(ids))!=len(ids): raise ValueError('Invalid meal list.')
            if any(not isinstance(k,str) or k not in FOODS or not allowed(k,family) for k in ids):
                raise ValueError('Unknown food or dietary conflict.')
            slots={'breakfast'} if meal=='Breakfast' else {'snack'} if meal=='Snack' else {'main','side'}
            if any(FOODS[k]['slot'] not in slots for k in ids): raise ValueError('Wrong meal category.')
    return plan

def demo_plan(family):
    b,m,s,n=[pool(family,x) for x in ['breakfast','main','side','snack']]
    if not all([b,m,n]): raise ValueError('Too few compatible recipes. Add recipes or review preferences; never remove an allergy to generate a plan.')
    def picks(arr,i,count): return list(dict.fromkeys(arr[(i+j)%len(arr)] for j in range(min(count,len(arr)))))
    return validate_plan([{'Breakfast':picks(b,i,2),'Lunch':picks(m,i,3)+picks(s,i,1),
                          'Dinner':picks(m,i+3,3)+picks(s,i+1,1),'Snack':picks(n,i,2)} for i in range(7)],family)

def secret(name,default=''):
    try: return str(st.secrets.get(name,os.getenv(name,default)))
    except (FileNotFoundError,KeyError): return os.getenv(name,default)

def ai_plan(family,key,model):
    from groq import Groq
    # No names, ages, measurements, or personal logs are sent to the provider.
    catalog={k:{'name':v['name'],'slot':v['slot'],'nutrition':nutrition(k)} for k,v in FOODS.items() if allowed(k,family)}
    request={'catalog':catalog,'estimated_targets':[targets(p) for p in family],
             'format':{'days':[{m:['food_id'] for m in MEALS}]}}
    response=Groq(api_key=key,timeout=35,max_retries=1).chat.completions.create(
        model=model,temperature=.3,max_tokens=3500,response_format={'type':'json_object'},
        messages=[{'role':'system','content':'Return JSON only with days: exactly 7 objects. Each object has Breakfast, Lunch, Dinner, Snack lists of 1-4 distinct catalog IDs. Use breakfast items for Breakfast, snack items for Snack, main/side for Lunch and Dinner. Choose varied shared desi meals; include protein-rich options. Do not invent foods or numbers. Portions are calculated separately by Python.'},
                  {'role':'user','content':json.dumps(request)}])
    return validate_plan(json.loads(response.choices[0].message.content)['days'],family)

def portion_rows(plan,family):
    rows=[]
    shares={'Breakfast':.25,'Lunch':.30,'Dinner':.30,'Snack':.15}
    for day,d in enumerate(plan,1):
        for p in family:
            t=targets(p)
            for meal,ids in d.items():
                target=[t['kcal']*shares[meal],t['protein']*shares[meal],t['carbs']*shares[meal],t['fat']*shares[meal]]
                # Fit calories and macros together, with practical serving bounds.
                matrix=[[nutrition(k)[i]/max(target[i],1) for k in ids] for i in range(4)]
                fit=lsq_linear(matrix,[1,1,1,1],bounds=(.25,2.5)).x
                for fid,q in zip(ids,fit):
                    q=round(float(q),2); nums=nutrition(fid)
                    rows.append(dict(day=day,member=p['name'],meal=meal,food_id=fid,food=FOODS[fid]['name'],
                                     servings=q,grams=round(FOODS[fid]['grams']*q),
                                     kcal=round(nums[0]*q),protein=round(nums[1]*q,1),carbs=round(nums[2]*q,1),fat=round(nums[3]*q,1)))
    return rows

def shopping(rows,pantry):
    sums={}
    for r in rows:
        for k,g in FOODS[r['food_id']]['ingredients'].items(): sums[k]=sums.get(k,0)+g*r['servings']
    return [{'ingredient':k,'needed_g':round(v,1),'pantry_g':pantry.get(k,0),
             'buy_g':round(max(0,v-pantry.get(k,0)),1)} for k,v in sorted(sums.items())]

def backup_import(raw):
    if len(raw)>1_000_000: raise ValueError('Backup too large.')
    obj=json.loads(raw)
    if obj.get('version')!=1: raise ValueError('Unsupported backup version.')
    family=obj.get('family')
    if not isinstance(family,list) or not 1<=len(family)<=8: raise ValueError('Backup needs 1-8 members.')
    for p in family: validate_profile(p)
    if len({p['name'] for p in family})!=len(family): raise ValueError('Duplicate member names.')
    if obj.get('plan'): validate_plan(obj['plan'],family)
    pantry=obj.get('pantry',{})
    if not isinstance(pantry,dict) or any(k not in ING or not isinstance(v,(int,float)) or not math.isfinite(v) or not 0<=v<=100000 for k,v in pantry.items()): raise ValueError('Invalid pantry.')
    logs=obj.get('logs',[])
    if not isinstance(logs,list) or len(logs)>10000: raise ValueError('Invalid logs.')
    for log in logs:
        if not isinstance(log,dict) or log.get('member') not in {p['name'] for p in family}: raise ValueError('Invalid log member.')
        date.fromisoformat(log['date'])
        if log.get('kind') not in MEALS+['Workout'] or log.get('status') not in ['Completed','Skipped']: raise ValueError('Invalid log.')
        if not isinstance(log.get('note',''),str) or len(log.get('note',''))>500: raise ValueError('Invalid note.')
    return dict(family=family,plan=obj.get('plan'),pantry=pantry,logs=logs)

def main():
    st.set_page_config(page_title='NutriNest',page_icon='🥗',layout='wide')
    st.markdown('<style>.stApp{background:#f6faf7}h1,h2,h3{color:#14543e}.stButton>button{border-radius:12px}</style>',unsafe_allow_html=True)
    st.title('🥗 NutriNest')
    st.write('One family. Shared desi meals. Personalized portions.')
    st.caption('Hackathon prototype • General wellness for adults aged 20–75 • Nutrition and portions are estimates, not prescriptions.')
    for k,v in dict(family=[],plan=None,logs=[],pantry={}).items():
        if k not in st.session_state: st.session_state[k]=v
    with st.sidebar:
        st.header('Your workspace')
        page=st.radio('Open',['Family','Meal planner','Shopping & cooking','Workouts','Progress','Backup & guide'])
        st.caption('Records are private to this browser session and may disappear on restart. Export a backup. No automatic long-term database storage.')
        mode=st.selectbox('Plan engine',['Demo (no API)','Groq AI'])
        model=st.text_input('Groq model',value=secret('GROQ_MODEL','openai/gpt-oss-20b'))
        st.caption('Configure GROQ_API_KEY in Streamlit Secrets or your environment. Never upload a real key to GitHub.')
    family=st.session_state.family
    if page=='Family':
        st.subheader('Family profiles')
        st.info('This MVP excludes children, pregnancy/breastfeeding, therapeutic diets, active injuries and eating-disorder care. Use qualified professional guidance for these cases.')
        if st.button('Load sample adult family'):
            st.session_state.family=[dict(name='Member A',age=42,sex='Male',height=175,weight=78,goal='Maintain',activity='Light',diet='Non-vegetarian',allergies=[],exclude=[]),
                                     dict(name='Member B',age=35,sex='Female',height=163,weight=64,goal='Maintain',activity='Light',diet='Vegetarian',allergies=[],exclude=[])]
            st.session_state.plan=None; st.session_state.logs=[]; st.rerun()
        with st.form('member'):
            a,b=st.columns(2)
            name=a.text_input('Member nickname',max_chars=50)
            age=a.number_input('Age',20,75,30)
            sex=a.selectbox('Sex used by the BMR equation',['Male','Female'])
            height=a.number_input('Height (cm)',130,220,170)
            weight=a.number_input('Weight (kg)',40.0,180.0,70.0,step=.5)
            goal=b.selectbox('Goal',GOALS)
            activity=b.selectbox('Activity level',list(ACTIVITY))
            diet=b.selectbox('Diet',['Non-vegetarian','Vegetarian','Vegan'])
            allergies=b.multiselect('Allergens to exclude',sorted(set(ALLERGEN.values())))
            exclude=b.multiselect('Disliked ingredients',list(ING))
            confirmed=st.checkbox('No excluded health circumstances apply; all relevant allergens are covered by this list.')
            if st.form_submit_button('Save member'):
                try:
                    if not confirmed: raise ValueError('Confirm eligibility before generating a wellness plan.')
                    p=validate_profile(dict(name=name.strip(),age=age,sex=sex,height=height,weight=weight,goal=goal,activity=activity,diet=diet,allergies=allergies,exclude=exclude))
                    if len(family)>=8: raise ValueError('Maximum eight members.')
                    if p['name'] in [x['name'] for x in family]: raise ValueError('Choose a unique nickname.')
                    st.session_state.family.append(p); st.session_state.plan=None; st.rerun()
                except ValueError as e: st.error(str(e))
        if family:
            st.dataframe(pd.DataFrame([{'Member':p['name'],**targets(p)} for p in family]),hide_index=True)
            st.caption('Mifflin–St Jeor BMR × activity factor; goal adjustment −10% / 0% / +5%. Demo macro allocation: 20% protein, 50% carbohydrate, 30% fat. No BMI diagnosis. Targets need individual review.')
            remove=st.selectbox('Remove member',[p['name'] for p in family])
            if st.button('Remove selected member'):
                st.session_state.family=[p for p in family if p['name']!=remove]
                st.session_state.logs=[l for l in st.session_state.logs if l['member']!=remove]
                st.session_state.plan=None; st.rerun()
    elif page=='Meal planner':
        st.subheader('Seven-day shared meal plan')
        st.warning('Shared meals obey the strictest family dietary exclusions. Ingredient checks cannot guarantee product-label or kitchen cross-contact safety. Check packaging and preparation yourself.')
        consent=st.checkbox('For Groq: allow anonymized nutrition targets and compatible food catalog to be sent to the AI provider.')
        if st.button('Generate seven-day plan',disabled=not family):
            try:
                with st.spinner('Planning meals…'):
                    if mode=='Groq AI':
                        if not consent: raise ValueError('Enable AI data consent or use Demo mode.')
                        if not secret('GROQ_API_KEY'): raise ValueError('GROQ_API_KEY is missing. Configure it or select Demo.')
                        result=ai_plan(family,secret('GROQ_API_KEY'),model)
                    else: result=demo_plan(family)
                    st.session_state.plan=result
                st.success('Plan generated. Review daily nutrient differences below.')
            except ValueError as e: st.error(str(e))
            except Exception: st.error('AI request failed or returned an invalid plan. Check model/key/quota, retry, or explicitly select Demo mode. Existing plan was retained.')
        if st.session_state.plan and family:
            rows=portion_rows(st.session_state.plan,family); df=pd.DataFrame(rows)
            day=st.selectbox('Day',list(range(1,8)))
            st.dataframe(df[df.day==day].drop(columns='food_id'),hide_index=True,width='stretch')
            totals=df.groupby(['day','member'])[['kcal','protein','carbs','fat']].sum().reset_index()
            for p in family:
                actual=totals[(totals.day==day)&(totals.member==p['name'])].iloc[0]; t=targets(p)
                st.write(f"**{p['name']}** — {actual.kcal:.0f} / {t['kcal']} kcal; protein {actual.protein:.0f} / {t['protein']} g; carbs {actual.carbs:.0f} / {t['carbs']} g; fat {actual.fat:.0f} / {t['fat']} g")
                gaps=[k for k in ['kcal','protein','carbs','fat'] if abs(actual[k]-t[k])/t[k]>.20]
                if gaps: st.warning('Target difference over 20% for '+p['name']+': '+', '.join(gaps)+'. Swap dishes or review with a professional. This is not a fully matched plan.')
            st.caption('Servings are bounded to 0.25–2.5 per dish. Grams are estimated cooked edible weights. Salt/spices and cooking water are not modeled; verify recipes before real use.')
            with st.expander('Swap one dish'):
                meal=st.selectbox('Meal',MEALS)
                old=st.selectbox('Current dish',st.session_state.plan[day-1][meal],format_func=lambda k:FOODS[k]['name'])
                opts=[k for k in pool(family,FOODS[old]['slot']) if k not in st.session_state.plan[day-1][meal]]
                if opts:
                    new=st.selectbox('Alternative',opts,format_func=lambda k:FOODS[k]['name'])
                    if st.button('Apply swap'):
                        d=st.session_state.plan[day-1][meal]; d[d.index(old)]=new; st.rerun()
                else: st.info('No compatible alternative in this catalog.')
            st.download_button('Download full meal plan CSV',df.to_csv(index=False),'nutrinest_meals.csv','text/csv')
        elif not family: st.info('Add family members or load the sample family first.')
    elif page=='Shopping & cooking':
        st.subheader('Pantry and shopping quantities')
        with st.form('pantry'):
            ingredient=st.selectbox('Ingredient',list(ING))
            amount=st.number_input('Already available (grams)',0.0,100000.0,0.0)
            if st.form_submit_button('Set available amount'): st.session_state.pantry[ingredient]=amount
        if st.session_state.plan and family:
            rows=portion_rows(st.session_state.plan,family)
            shop=pd.DataFrame(shopping(rows,st.session_state.pantry))
            st.dataframe(shop,hide_index=True,width='stretch')
            st.download_button('Download shopping list',shop.to_csv(index=False),'nutrinest_shopping.csv','text/csv')
            day=st.selectbox('Cooking day',list(range(1,8)))
            selected=[r for r in rows if r['day']==day]
            st.write('Total family servings and estimated cooked quantity')
            st.dataframe(pd.DataFrame(selected).groupby(['meal','food'])[['servings','grams']].sum().reset_index(),hide_index=True)
            st.write('Ingredients for this day (before pantry deduction)')
            st.dataframe(pd.DataFrame(shopping(selected,{}))[['ingredient','needed_g']],hide_index=True)
        else: st.info('Generate a meal plan first.')
    elif page=='Workouts':
        st.subheader('Weekly activity planner')
        st.caption('Template-based suggestions, not AI-generated medical or rehabilitation advice. Stop an activity that causes pain.')
        if not family: st.info('Add a member first.'); return
        person=st.selectbox('Member',[p['name'] for p in family])
        location=st.selectbox('Location',['Home','Gym','Outdoors'])
        equipment=st.selectbox('Equipment',['None','Dumbbells','Resistance band'])
        level=st.selectbox('Experience',['Beginner','Intermediate'])
        duration=st.selectbox('Minutes available',[10,20,30,45])
        days=st.multiselect('Workout days',['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'],default=['Monday','Wednesday','Friday'])
        pain=st.checkbox('Current pain, injury or medical exercise restriction')
        if pain: st.warning('Personal workout generation paused. Ask a qualified professional for a suitable activity plan.'); return
        p=next(p for p in family if p['name']==person)
        if days:
            schedule=[]
            for i,d in enumerate(['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']):
                strength='Chair sit-to-stand, wall push-up, calf raise'
                if equipment=='Dumbbells': strength='Light goblet squat, supported dumbbell row, calf raise'
                if equipment=='Resistance band': strength='Chair sit-to-stand, controlled band row, calf raise'
                session=('Comfortable walk' if p['goal']=='Weight loss' or i%2 else strength)
                schedule.append({'day':d,'member':person,'location':location,'session':session if d in days else 'Rest / comfortable everyday movement',
                                 'minutes':duration if d in days else 0})
            st.dataframe(pd.DataFrame(schedule),hide_index=True)
            st.write('Include an easy warm-up and cool-down within your selected time. Strength template: '+('1' if level=='Beginner' else '2')+' set(s) of 6–10 comfortable repetitions, resting as needed. Avoid consecutive demanding sessions.')
            st.download_button('Download workout schedule',pd.DataFrame(schedule).to_csv(index=False),'nutrinest_workouts.csv','text/csv')
    elif page=='Progress':
        st.subheader('Daily check-in')
        if not family: st.info('Add a member first.'); return
        with st.form('log'):
            person=st.selectbox('Member',[p['name'] for p in family])
            when=st.date_input('Date',date.today(),max_value=date.today())
            kind=st.selectbox('Record',MEALS+['Workout'])
            status=st.selectbox('Status',['Completed','Skipped'])
            note=st.text_input('What did you eat/do? Optional details',max_chars=500)
            if st.form_submit_button('Save check-in'):
                key=(person,when.isoformat(),kind)
                st.session_state.logs=[l for l in st.session_state.logs if (l['member'],l['date'],l['kind'])!=key]
                st.session_state.logs.append(dict(member=person,date=when.isoformat(),kind=kind,status=status,note=note))
                st.success('Saved. Saving the same member/date/type updates its existing record.')
        logs=st.session_state.logs
        if logs:
            frame=pd.DataFrame(logs); cutoff=(date.today()-timedelta(days=6)).isoformat()
            recent=frame[(frame.date>=cutoff)&(frame.date<=date.today().isoformat())]
            st.metric('Completed / logged entries (last 7 days)',f"{100*(recent.status=='Completed').mean():.0f}%" if len(recent) else 'No entries')
            st.caption('This measures logged entries only; it is not adherence to all scheduled meals or a medical outcome.')
            st.dataframe(frame.sort_values('date',ascending=False),hide_index=True)
            if len(recent): st.bar_chart(recent.assign(completed=recent.status.eq('Completed').astype(int)).groupby('member').completed.sum())
            st.download_button('Export logs CSV',frame.to_csv(index=False),'nutrinest_logs.csv','text/csv')
    else:
        st.subheader('Backup and deployment guide')
        data={'version':1,**{k:st.session_state[k] for k in ['family','plan','pantry','logs']}}
        st.download_button('Export private backup JSON',json.dumps(data,indent=2),'nutrinest_backup.json','application/json')
        upload=st.file_uploader('Restore backup JSON',type=['json'])
        confirm=st.checkbox('Replace current session with this backup')
        if st.button('Restore backup',disabled=not upload or not confirm):
            try:
                restored=backup_import(upload.getvalue())
                for k,v in restored.items(): st.session_state[k]=v
                st.success('Backup restored.'); st.rerun()
            except Exception: st.error('Invalid backup; current data was not changed.')
        clear=st.checkbox('Confirm deletion of all current session records')
        if st.button('Clear session records',disabled=not clear):
            for k,v in dict(family=[],plan=None,logs=[],pantry={}).items(): st.session_state[k]=v
            st.rerun()
        st.code('pip install -r requirements.txt\nstreamlit run app.py',language='bash')
        st.write('Upload app.py and requirements.txt to GitHub. On Streamlit Community Cloud, choose that repository and app.py. Add the following in app Secrets:')
        st.code('GROQ_API_KEY = "your-key"\nGROQ_MODEL = "openai/gpt-oss-20b"',language='toml')
        st.markdown('API setup: https://console.groq.com/keys • Nutrition curation: https://fdc.nal.usda.gov/')
        st.write('Limitations: 26 illustrative recipes, no live food prices, no guaranteed macro matching, no background notifications, no database or clinical validation. Workouts use local templates. AI selects meal IDs; numerical calculations stay in Python.')
        with st.expander('Inspect food catalog and recipe quantities'):
            st.dataframe(pd.DataFrame([dict(id=k,**v,kcal=round(nutrition(k)[0])) for k,v in FOODS.items()]),hide_index=True)

if __name__=='__main__':
    main()
