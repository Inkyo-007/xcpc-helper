class Poly {
private:
	using ld = long double; //精度足够时可以修改为 double 加速
	static constexpr ld PI = acos(-1);
	using cd = complex <ld>;
	
	vector <ld> a;
	void normalize() { //在题目保留后缀 0 项时不要使用该函数
		while(!a.empty() && a.back() == 0) a.pop_back();
	}
	
	static void fft(vector <cd> &a, bool flag){ //false : DFT; true : IDFT
		int n = a.size();
		assert((n & (n - 1)) == 0);
		vector <int> rev(n, 0);
		int k = __builtin_ctz(n);
		for(int i = 0; i < n; i ++){
			rev[i] = (rev[i >> 1] >> 1) | ((i & 1) << (k - 1));
		}
		for(int i = 0; i < n; i ++){
			if(i < rev[i]) swap(a[i], a[rev[i]]);
		}
		for(int l = 1; l < n; l <<= 1){
			cd wn(cos(2 * PI / (2 * l)), (flag ? -1 : 1) * sin(2 * PI / (2 * l)));
			for(int i = 0; i < n; i += l * 2){
				cd w(1, 0);
				for(int k = 0; k < l; k ++){
					cd u = a[i + k];
					cd v = w * a[i + k + l];
					a[i + k] = u + v;
					a[i + k + l] = u - v;
					w *= wn;
				}
			}
		}
		if(flag){
			for(int i = 0; i < n; i ++) a[i] /= n;
		}
	}
	
public:
	Poly() {}
	Poly(int n) : a(n) {}
	
	template <typename T>
	Poly(const T& c) {
		a.reserve(c.size());
		for (auto&& x : c) {
			a.push_back(static_cast<ld>(x));
		}
	}
	
	int size() const { return a.size(); }
	ld get(int x) { return a[x]; }
	
	friend Poly operator + (const Poly& A, const Poly& B) {
		Poly C;
		int n = max(A.size(), B.size());
		C.a.resize(n);
		for (int i = 0; i < n; i++) {
			if (i < A.size()) C.a[i] += A.a[i];
			if (i < B.size()) C.a[i] += B.a[i];
		}
		C.normalize();
		return C;
	}
	
	friend Poly operator - (const Poly& A, const Poly& B) {
		Poly C;
		int n = max(A.size(), B.size());
		C.a.resize(n);
		for (int i = 0; i < n; i++) {
			if (i < A.size()) C.a[i] += A.a[i];
			if (i < B.size()) C.a[i] -= B.a[i];
		}
		C.normalize();
		return C;
	}
	
	friend Poly operator * (const Poly& A, const Poly& B) {
		if (A.a.empty() || B.a.empty()) return Poly();
		
		int n = A.size(), m = B.size();
		int s = 1;
		while (s < n + m - 1) s <<= 1;
		
		vector <cd> fa(s), fb(s);
		for (int i = 0; i < n; i++) fa[i] = A.a[i];
		for (int i = 0; i < m; i++) fb[i] = B.a[i];
		
		fft(fa, false), fft(fb, false);
		for (int i = 0; i < s; i++) fa[i] *= fb[i];
		fft(fa, true);
		
		Poly C;
		C.a.resize(n + m - 1);
		for (int i = 0; i < n + m - 1; i++) {
			C.a[i] = fa[i].real();
		}
		C.normalize();
		return C;
	}
};