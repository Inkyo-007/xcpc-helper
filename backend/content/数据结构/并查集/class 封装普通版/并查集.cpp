class DSU {
private:
	int n;
	vector <int> fa;
	
public:
	DSU () {}
	DSU (int _n) {
		init(_n);
	}
	void init(int _n) {
		n = _n;
		fa.resize(n + 1);
		iota(fa.begin() + 1, fa.end(), 1);
	}
	int find(int x){
		while(x != fa[x]) x = fa[x] = fa[fa[x]];
		return x;
	}
	void merge(int x, int y){
		x = find(x), y = find(y);
		if(x == y) return;
		fa[y] = x;
	}
	bool same(int x, int y){
		return find(x) == find(y);
	}
};