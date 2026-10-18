from pathlib import Path
import re
import sympy as sp
import pymupdf
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Flowable

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'output' / 'pdf'
OUT.mkdir(parents=True, exist_ok=True)
DEST = OUT / '习题四_2、5、7、8、9、12、13题_详细解析.pdf'
pdfmetrics.registerFont(TTFont('Song', r'C:\Windows\Fonts\simsun.ttc'))
pdfmetrics.registerFont(TTFont('Hei', r'C:\Windows\Fonts\simhei.ttf'))
pdfmetrics.registerFont(TTFont('TimesMath', r'C:\ProgramData\Anaconda3\Lib\site-packages\matplotlib\mpl-data\fonts\ttf\DejaVuSans.ttf'))
NAVY = colors.HexColor('#173653')
BODY = ParagraphStyle('Body', fontName='Song', fontSize=11, leading=19, spaceAfter=8, wordWrap='CJK')
HEAD = ParagraphStyle('Head', parent=BODY, fontName='Hei', fontSize=17, leading=24, textColor=NAVY, spaceAfter=15)
SUB = ParagraphStyle('Sub', parent=HEAD, fontSize=12, leading=20, spaceBefore=7, spaceAfter=8)
FORM = ParagraphStyle('Formula', parent=BODY, fontName='TimesMath', fontSize=12, leading=22, leftIndent=16, spaceAfter=10)
ANSWER = ParagraphStyle('Answer', parent=BODY, fontName='Song', backColor=colors.HexColor('#eef4f8'), borderPadding=9, spaceBefore=7, spaceAfter=15)
story = []

def text(value, style=BODY):
    story.append(Paragraph(normalize(value), style))

def normalize(value):
    value = value.replace('−', '-').replace('ℓ', 'r')
    for glyph in '⋯⋮⋱':
        value = value.replace(glyph, '<font name="TimesMath">'+glyph+'</font>')
    for glyph, replacement in zip('₀₁₂₃₄₅₆₇₈₉ₘₙᵢⱼ', ['0','1','2','3','4','5','6','7','8','9','m','n','i','j']):
        value = value.replace(glyph, '<sub>'+replacement+'</sub>')
    for glyph, replacement in zip('⁰¹²³', '0123'):
        value = value.replace(glyph, '<super>'+replacement+'</super>')
    return value

def formula(value):
    text(value, FORM)

def heading(value):
    text(value, HEAD)

def sub(value):
    text(value, SUB)

def answer(value):
    text(value, ANSWER)

def page():
    story.append(PageBreak())

class Matrix(Flowable):
    def __init__(self, rows, label='A =', widths=None):
        super().__init__()
        self.rows = rows
        self.label = label
        self.widths = widths or [60] * len(rows[0])
        self.height = 20 * len(rows) + 10
        self.width = sum(self.widths) + 90

    def draw(self):
        drawing = self.canv
        drawing.setFont('TimesMath', 12)
        drawing.drawString(8, self.height / 2 - 4, self.label)
        left = 65
        right = left + sum(self.widths)
        drawing.setStrokeColor(NAVY)
        for edge, direction in [(left, 1), (right, -1)]:
            drawing.line(edge, 4, edge, self.height - 4)
            drawing.line(edge, 4, edge + direction * 6, 4)
            drawing.line(edge, self.height - 4, edge + direction * 6, self.height - 4)
        for row_index, row in enumerate(self.rows):
            horizontal = left
            for entry, width in zip(row, self.widths):
                paragraph = Paragraph(normalize(str(entry)), ParagraphStyle('Cell', parent=FORM, alignment=TA_CENTER, leftIndent=0, leading=18, spaceAfter=0))
                _, height = paragraph.wrap(width, 24)
                paragraph.drawOn(drawing, horizontal, self.height - 5 - row_index * 20 - height)
                horizontal += width

def matrix(rows, label='A =', widths=None):
    story.append(Matrix(rows, label, widths))
    story.append(Spacer(1, 8))

heading('习题四 · 指定题目详细解析')
text('《线性代数与解析几何》第2版', SUB)
text('题号：2、5、7、8、9、12、13（含第7题全部5个小题）。')
text('题目位置：教材印刷页113—114；所提供PDF的第123—124页。以下以 I 表示单位矩阵，O 表示零矩阵，A<super>T</super> 表示转置。')
heading('第2题  对称与反对称分解')
text('题目：证明每个方阵都可以表示为一个对称矩阵与一个反对称矩阵之和。')
text('思路：转置时，对称部分保持不变，反对称部分改变符号。因此将 A 与其转置相加、相减即可分离这两部分。')
formula('S = (A + A<super>T</super>)/2,　K = (A − A<super>T</super>)/2.')
formula('S<super>T</super> = (A<super>T</super> + A)/2 = S,')
formula('K<super>T</super> = (A<super>T</super> − A)/2 = −K,　S + K = A.')
answer('结论：A = (A + A<super>T</super>)/2 + (A − A<super>T</super>)/2，前者对称，后者反对称。')
text('补充：分解还具有唯一性。若 A = S + K，则 A<super>T</super> = S − K；两式相加、相减，必得到上述 S、K。')
heading('第5题  行向量、矩阵与列向量的乘积')
text('题目：计算 x<super>T</super>Ay，其中 x = (x₁,…,xₘ)<super>T</super>，y = (y₁,…,yₙ)<super>T</super>，A = (a<sub>ij</sub>) 为 m×n 矩阵。')
text('先计算 Ay：其第 i 个分量为 a<sub>i1</sub>y₁ + ⋯ + a<sub>in</sub>yₙ。再用行向量 x<super>T</super> 左乘，即用 x<sub>i</sub> 乘各分量后求和。')
formula('x<super>T</super>Ay = ∑<sub>i=1</sub><super>m</super> x<sub>i</sub>(∑<sub>j=1</sub><super>n</super> a<sub>ij</sub>y<sub>j</sub>) = ∑<sub>i=1</sub><super>m</super>∑<sub>j=1</sub><super>n</super> a<sub>ij</sub>x<sub>i</sub>y<sub>j</sub>.')
answer('答案：上述二重求和。结果是一个数（1×1矩阵），不是向量。')

page()
heading('第7题  方阵的 k 次幂（1）—（2）')
text('以下 k 均为正整数。')
sub('（1）三角函数型矩阵')
matrix([['cos θ','sin θ'],['−sin θ','cos θ']])
text('记该矩阵为 R(θ)。按矩阵乘法并使用三角函数和角公式，可得：')
formula('R(α)R(β) = R(α + β).')
text('例如乘积的第一行依次为 cos α cos β − sin α sin β = cos(α+β)，以及 cos α sin β + sin α cos β = sin(α+β)，第二行同理。连续相乘 k 次即得：')
matrix([['cos(kθ)','sin(kθ)'],['−sin(kθ)','cos(kθ)']], 'A^k =', [100,100])
answer('答案：将原矩阵中的 θ 换为 kθ。注意左下角始终带负号。')
sub('（2）矩阵 A = [[a,b],[−b,a]]')
text('当 a、b 为实数时，令 r = √(a²+b²)。若 r = 0，则 a = b = 0，A 的任意正整数次幂都是 O。')
text('若 r &gt; 0，取角 φ 满足 cos φ = a/r、sin φ = b/r，则 A = rR(φ)。利用（1）得到：')
matrix([['cos(kφ)','sin(kφ)'],['−sin(kφ)','cos(kφ)']], 'A^k = r^k', [100,100])
text('无需选择角度的通用代数写法：令 u = ((a+ib)<super>k</super>+(a−ib)<super>k</super>)/2，v = ((a+ib)<super>k</super>−(a−ib)<super>k</super>)/(2i)。')
matrix([['u','v'],['−v','u']], 'A^k =')
text('其中 i² = −1。因为 J = [[0,1],[−1,0]] 满足 J² = −I，将 A = aI+bJ 用二项式展开并分别合并偶次、奇次项，即得该式；此代数形式对复数 a、b 也成立。')

page()
heading('第7题（3）  四阶矩阵的幂')
matrix([['1','a','1','0'],['0','1','0','1'],['0','0','1','a'],['0','0','0','1']])
sub('第一步：拆成单位矩阵与幂零矩阵之和')
text('令 A = I + N，则')
matrix([['0','a','1','0'],['0','0','0','1'],['0','0','0','a'],['0','0','0','0']], 'N =')
sub('第二步：计算 N 的低次幂')
text('N² 只有第(1,4)个元素可能非零，其值为 N₁₂N₂₄ + N₁₃N₃₄ = a·1 + 1·a = 2a。由于 N 的第4行全为零，再右乘 N 就得到零矩阵。')
matrix([['0','0','0','2a'],['0','0','0','0'],['0','0','0','0'],['0','0','0','0']], 'N² =')
formula('N³ = O.')
sub('第三步：使用二项式展开')
text('I 与 N 可交换，故二项式公式适用。N³ 及更高次项均为零，于是')
formula('A<super>k</super> = (I+N)<super>k</super> = I + kN + [k(k−1)/2]N².')
matrix([['1','ka','k','k(k−1)a'],['0','1','0','k'],['0','0','1','ka'],['0','0','0','1']], 'A^k =', [48,48,48,115])
answer('关键：右上角是 k(k−1)a，而不是 k²a；它来自 N² 项。')

page()
heading('第7题（4）—（5）  结构化矩阵的幂')
sub('（4）主对角线与第一条上对角线为1的 n 阶矩阵')
text('题设 A 的其余元素全为0。令 A = I+N，其中 N 的第(i,i+1)个元素为1，其余为0。')
text('N 的作用是将非零位置沿上对角线移动一格。因此 N<super>r</super> 的第 r 条上对角线全为1，其余为0；N<super>n</super> = O。约定 N⁰ = I。')
formula('A<super>k</super> = ∑<sub>r=0</sub><super>min(k,n−1)</super> C(k,r)N<super>r</super>.')
text('于是第(i,j)个元素为：当 j ≥ i 时，(A<super>k</super>)<sub>ij</sub> = C(k,j−i)；当 j &lt; i 时，该元素为0。这里 C(k,r) = k!/[r!(k−r)!]（0≤r≤k），r&gt;k 时约定为0。')
matrix([['1','k','C(k,2)','⋯','C(k,n−1)'],['0','1','k','⋯','C(k,n−2)'],['⋮','⋮','⋱','⋱','⋮'],['0','0','⋯','1','k'],['0','0','⋯','0','1']], 'A^k =', [40,40,65,40,100])
answer('答案：主对角线为1，第 r 条上对角线为 C(k,r)。特别地，r&gt;k 时该条上对角线全为0。')
sub('（5）元素为 aᵢbⱼ 的 n 阶矩阵')
text('令 α = (a₁,…,aₙ)<super>T</super>、β = (b₁,…,bₙ)<super>T</super>，则 A = αβ<super>T</super>。其中 β<super>T</super>α 是一个数，记为 s：')
formula('s = β<super>T</super>α = ∑<sub>i=1</sub><super>n</super> a<sub>i</sub>b<sub>i</sub>.')
formula('A² = (αβ<super>T</super>)(αβ<super>T</super>) = α(β<super>T</super>α)β<super>T</super> = sA.')
text('继续相乘：A³ = sA² = s²A。由数学归纳法，若 A<super>k</super> = s<super>k−1</super>A，则 A<super>k+1</super> = s<super>k−1</super>A² = s<super>k</super>A。')
answer('答案：k=1 时 A¹=A；k≥2 时 A<super>k</super> = (∑ aᵢbᵢ)<super>k−1</super>A。若 s=0，则所有 k≥2 都有 A<super>k</super>=O；单独列出 k=1 可避免 0⁰ 的歧义。')

page()
heading('第8题  对称矩阵的乘积')
text('题目：设 A、B 都是 n 阶对称方阵，且 AB = BA。证明 AB 也是对称方阵。')
text('证明：因为 A、B 对称，所以 A<super>T</super>=A，B<super>T</super>=B。对乘积取转置时，必须颠倒因子的顺序：')
formula('(AB)<super>T</super> = B<super>T</super>A<super>T</super> = BA = AB.')
answer('因此 AB 等于自身的转置，所以 AB 是对称矩阵。')
text('注意：条件 AB=BA 不能省略。对称矩阵的乘积未必对称；事实上，在 A、B 都对称的前提下，AB 对称当且仅当 AB=BA。')
heading('第9题  三角矩阵的乘积')
text('题目：证明两个 n 阶上（下）三角形方阵的乘积仍为上（下）三角形方阵。')
sub('（一）上三角情形')
text('设 A=(a<sub>ij</sub>)、B=(b<sub>ij</sub>) 均为上三角矩阵，记 C=AB=(c<sub>ij</sub>)。要证 C 上三角，只需证明 i&gt;j 时 c<sub>ij</sub>=0。')
formula('c<sub>ij</sub> = ∑<sub>ℓ=1</sub><super>n</super> a<sub>iℓ</sub>b<sub>ℓj</sub>.')
text('固定 i&gt;j。对每个求和指标 ℓ 分两种情况：')
text('① 若 ℓ&lt;i，则 a<sub>iℓ</sub>=0，因为它位于 A 的主对角线下方。<br/>② 若 ℓ≥i，则 ℓ≥i&gt;j，故 b<sub>ℓj</sub>=0，因为它位于 B 的主对角线下方。')
text('所以每项 a<sub>iℓ</sub>b<sub>ℓj</sub> 都为0，c<sub>ij</sub>=0，AB 为上三角矩阵。')
sub('（二）下三角情形')
text('设 A、B 均为下三角矩阵。固定 i&lt;j，仍使用上面的乘积元素公式。')
text('① 若 ℓ≤i，则 ℓ≤i&lt;j，故 b<sub>ℓj</sub>=0。<br/>② 若 ℓ&gt;i，则 a<sub>iℓ</sub>=0。')
text('每项仍为0，因此 i&lt;j 时 c<sub>ij</sub>=0，AB 为下三角矩阵。')
answer('结论：同为上三角，乘积仍上三角；同为下三角，乘积仍下三角。这里并不是指一个上三角与一个下三角的乘积。')

page()
heading('第12题  多个可逆矩阵乘积的逆')
text('题目：设 A₁、A₂、…、A<sub>k</sub> 都是 n 阶可逆方阵。证明：')
formula('(A₁A₂⋯A<sub>k</sub>)<super>−1</super> = A<sub>k</sub><super>−1</super>⋯A₂<super>−1</super>A₁<super>−1</super>.')
text('证明：记 P=A₁A₂⋯A<sub>k</sub>，Q=A<sub>k</sub><super>−1</super>⋯A₂<super>−1</super>A₁<super>−1</super>。利用乘法结合律，从中间开始将互为逆矩阵的相邻因子配对消去：')
formula('PQ = A₁⋯A<sub>k−1</sub>(A<sub>k</sub>A<sub>k</sub><super>−1</super>)A<sub>k−1</sub><super>−1</super>⋯A₁<super>−1</super> = ⋯ = I.')
text('反向乘积中，则从 A₁<super>−1</super>A₁ 开始依次消去：')
formula('QP = A<sub>k</sub><super>−1</super>⋯A₂<super>−1</super>(A₁<super>−1</super>A₁)A₂⋯A<sub>k</sub> = ⋯ = I.')
answer('由逆矩阵定义，P 可逆且 P<super>−1</super>=Q。口诀：乘积求逆，顺序倒过来，逐个取逆。不能擅自交换矩阵次序。')
heading('第13题  幂零矩阵加单位矩阵的逆')
text('题目：设方阵 A 满足 A<super>k</super>=O，k 为正整数。证明 I+A 可逆，并求 (I+A)<super>−1</super>。')
text('思路：仿照有限等比数列求和，构造交错符号的矩阵多项式：')
formula('S = ∑<sub>r=0</sub><super>k−1</super>(−1)<super>r</super>A<super>r</super> = I − A + A² − ⋯ + (−1)<super>k−1</super>A<super>k−1</super>.')
text('展开 (I+A)S=S+AS。常数项为 I；对每个 1≤r≤k−1，A<super>r</super> 的系数为 (−1)<super>r</super>+(−1)<super>r−1</super>=0。因此中间项两两抵消，只剩：')
formula('(I+A)S = I + (−1)<super>k−1</super>A<super>k</super> = I.')
text('又因为 S 是 A 的多项式，A 与 S 可交换，故 S(I+A)=(I+A)S=I。由逆矩阵定义即得：')
answer('(I+A)<super>−1</super> = I − A + A² − ⋯ + (−1)<super>k−1</super>A<super>k−1</super>。')
text('边界检查：k=1 时 A=O，逆矩阵为 I；k=2 时逆矩阵为 I−A；k=3 时逆矩阵为 I−A+A²。此处为有限和，不涉及无穷级数的收敛性。')

def footer(drawing, document):
    drawing.saveState()
    drawing.setStrokeColor(colors.HexColor('#c9d5df'))
    drawing.line(46, 802, 549, 802)
    drawing.setFont('Song', 9)
    drawing.setFillColor(NAVY)
    drawing.drawString(46, 812, '线性代数与解析几何 · 习题四解析')
    drawing.drawRightString(549, 28, f'{document.page}')
    drawing.restoreState()

parameter = sp.symbols('a')
original = sp.Matrix([[1,parameter,1,0],[0,1,0,1],[0,0,1,parameter],[0,0,0,1]])
for exponent in range(1, 9):
    expected = sp.Matrix([[1,exponent*parameter,exponent,exponent*(exponent-1)*parameter],[0,1,0,exponent],[0,0,1,exponent*parameter],[0,0,0,1]])
    assert original**exponent == expected
for dimension in range(1, 7):
    nilpotent = sp.zeros(dimension)
    for index in range(dimension-1):
        nilpotent[index,index+1] = 1
    for exponent in range(1, 8):
        expected = sp.Matrix(dimension,dimension,lambda row,column: sp.binomial(exponent,column-row) if column>=row else 0)
        assert (sp.eye(dimension)+nilpotent)**exponent == expected
    inverse = sum(((-1)**power * nilpotent**power for power in range(dimension)),sp.zeros(dimension))
    assert (sp.eye(dimension)+nilpotent)*inverse == sp.eye(dimension)

document = SimpleDocTemplate(str(DEST), pagesize=(595.276,841.89), rightMargin=46, leftMargin=46, topMargin=55, bottomMargin=48, title='习题四：2、5、7、8、9、12、13题详细解析', author='习题解析')
document.build(story, onFirstPage=footer, onLaterPages=footer)
pdf = pymupdf.open(DEST)
print('OUTPUT',DEST)
print('PAGES',len(pdf))
for index, sheet in enumerate(pdf):
    sheet.get_pixmap(matrix=pymupdf.Matrix(1.5,1.5)).save(str(ROOT / 'tmp' / 'pdfs' / f'answer_{index+1}.png'))
    extracted = sheet.get_text()
    assert '\ufffd' not in extracted and '\x00' not in extracted
    print('PAGE',index+1,'CHARS',len(extracted),'FIRST',extracted.splitlines()[1:4])
    for block in sheet.get_text('blocks'):
        assert block[0]>=35 and block[2]<=560, (index,block)
print('SYMBOLIC_AND_LAYOUT_CHECKS_OK')
