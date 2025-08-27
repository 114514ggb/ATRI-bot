#include <Python.h>
#include <string.h>
#include <stdlib.h>


int levenshtein_distance(const char* s1, const char* s2) {
    int len1 = strlen(s1);
    int len2 = strlen(s2);
    
    // 如果其中一个字符串为空，返回另一个字符串的长度
    if (len1 == 0) return len2;
    if (len2 == 0) return len1;
    
    // 创建距离矩阵
    int** matrix = (int**)malloc((len1 + 1) * sizeof(int*));
    for (int i = 0; i <= len1; i++) {
        matrix[i] = (int*)malloc((len2 + 1) * sizeof(int));
    }
    
    // 初始化第一行和第一列
    for (int i = 0; i <= len1; i++) {
        matrix[i][0] = i;
    }
    for (int j = 0; j <= len2; j++) {
        matrix[0][j] = j;
    }
    
    // 填充距离矩阵
    for (int i = 1; i <= len1; i++) {
        for (int j = 1; j <= len2; j++) {
            int cost = (s1[i-1] == s2[j-1]) ? 0 : 1;
            
            int deletion = matrix[i-1][j] + 1;
            int insertion = matrix[i][j-1] + 1;
            int substitution = matrix[i-1][j-1] + cost;
            
            // 取最小值
            int min_val = deletion;
            if (insertion < min_val) min_val = insertion;
            if (substitution < min_val) min_val = substitution;
            
            matrix[i][j] = min_val;
        }
    }
    
    int result = matrix[len1][len2];
    
    // 释放内存
    for (int i = 0; i <= len1; i++) {
        free(matrix[i]);
    }
    free(matrix);
    
    return result;
}

// Python包装函数
static PyObject* py_levenshtein_distance(PyObject* self, PyObject* args) {
    const char* s1;
    const char* s2;
    
    // 解析Python参数
    if (!PyArg_ParseTuple(args, "ss", &s1, &s2)) {
        return NULL;
    }
    
    // 调用C函数计算距离
    int distance = levenshtein_distance(s1, s2);
    
    // 返回Python整数对象
    return PyLong_FromLong(distance);
}

// 计算相似度百分比的函数
static PyObject* py_levenshtein_similarity(PyObject* self, PyObject* args) {
    const char* s1;
    const char* s2;
    
    if (!PyArg_ParseTuple(args, "ss", &s1, &s2)) {
        return NULL;
    }
    
    int len1 = strlen(s1);
    int len2 = strlen(s2);
    int max_len = (len1 > len2) ? len1 : len2;
    
    if (max_len == 0) {
        return PyFloat_FromDouble(100.0);
    }
    
    int distance = levenshtein_distance(s1, s2);
    double similarity = (1.0 - (double)distance / max_len) * 100.0;
    
    return PyFloat_FromDouble(similarity);
}

// 方法定义
static PyMethodDef LevenshteinMethods[] = {
    {"distance", py_levenshtein_distance, METH_VARARGS, 
     "Calculate Levenshtein distance between two strings"},
    {"similarity", py_levenshtein_similarity, METH_VARARGS,
     "Calculate similarity percentage between two strings"},
    {NULL, NULL, 0, NULL}
};

// 模块定义
static struct PyModuleDef levenshteinmodule = {
    PyModuleDef_HEAD_INIT,
    "levenshtein",
    "Fast Levenshtein distance implementation in C",
    -1,
    LevenshteinMethods
};

// 模块初始化函数
PyMODINIT_FUNC PyInit_levenshtein(void) {
    return PyModule_Create(&levenshteinmodule);
}