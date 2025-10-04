from __future__ import annotations
import random
from dataclasses import dataclass
from typing import List

@dataclass
class QA:
    category: str
    question: str
    options: List[str]
    correct_index: int

# Required categories
CATEGORIES = ["DSA", "Cloud", "Cybersecurity", "DevOps", "AI/ML", "Data Science", "General CS"]

# === EXPANDED BANK (~56 Qs; add more freely) ===
BANK: List[QA] = [
    # ---------------- DSA (8) ----------------
    QA("DSA", "Time complexity of binary search on a sorted array?",
       ["O(n)", "O(log n)", "O(n log n)", "O(1)"], 1),
    QA("DSA", "Which DS best implements a FIFO queue?",
       ["Array", "Linked List", "Stack", "Hash Map"], 1),
    QA("DSA", "Average time to access an element by index in a Python list?",
       ["O(1)", "O(log n)", "O(n)", "O(n log n)"], 0),
    QA("DSA", "What traversal prints BST keys in ascending order?",
       ["Preorder", "Inorder", "Postorder", "Level order"], 1),
    QA("DSA", "Which DS supports LIFO naturally?",
       ["Queue", "Deque", "Stack", "Priority Queue"], 2),
    QA("DSA", "Which structure gives expected O(1) lookup by key?",
       ["Hash Table", "Binary Heap", "BST", "Queue"], 0),
    QA("DSA", "Dijkstra’s algorithm needs weights to be:",
       ["Negative", "Non-negative", "Zero", "All distinct"], 1),
    QA("DSA", "Which DS is best for implementing recursion manually?",
       ["Stack", "Queue", "Heap", "Graph"], 0),

    # ---------------- Cloud (8) ----------------
    QA("Cloud", "Which service model gives you control of apps but not the OS?",
       ["IaaS", "PaaS", "SaaS", "FaaS"], 1),
    QA("Cloud", "Which AWS service is object storage?",
       ["EBS", "EFS", "S3", "RDS"], 2),
    QA("Cloud", "Which best describes horizontal scaling?",
       ["Bigger server", "More servers", "Faster disk", "More RAM"], 1),
    QA("Cloud", "Kubernetes object that exposes Pods to the network:",
       ["Deployment", "Service", "ConfigMap", "Secret"], 1),
    QA("Cloud", "Which Azure service is a managed Postgres database?",
       ["Cosmos DB", "Azure SQL", "Azure Database for PostgreSQL", "Table Storage"], 2),
    QA("Cloud", "GCP object storage offering:",
       ["Filestore", "Persistent Disk", "Cloud Storage", "Bigtable"], 2),
    QA("Cloud", "Which pattern reduces cold starts for serverless?",
       ["Prewarming", "Blue/Green", "Sharding", "Fan-out"], 0),
    QA("Cloud", "Infra as Code tool primarily for provisioning cloud resources:",
       ["Jenkins", "Terraform", "Prometheus", "Fluentd"], 1),

    # ------------- Cybersecurity (8) -------------
    QA("Cybersecurity", "CIA triad stands for:",
       ["Confidentiality, Integrity, Availability",
        "Control, Inspection, Authorization",
        "Confidentiality, Identity, Access",
        "Containment, Integrity, Audit"], 0),
    QA("Cybersecurity", "Salting passwords primarily prevents:",
       ["SQL injection", "Rainbow table attacks", "Buffer overflow", "XSS"], 1),
    QA("Cybersecurity", "Which auth factor is 'something you are'?",
       ["Password", "TOTP app", "Fingerprint", "Security question"], 2),
    QA("Cybersecurity", "Principle of least privilege means:",
       ["Read-only logs", "Only minimal required access", "No admin", "Air-gap"], 1),
    QA("Cybersecurity", "Common mitigation for SQL injection:",
       ["Input length cap", "Parameterized queries", "Regex only", "WAF off"], 1),
    QA("Cybersecurity", "Which attack intercepts traffic on open Wi-Fi?",
       ["DoS", "MITM", "Phishing", "RCE"], 1),
    QA("Cybersecurity", "HSTS primarily protects against:",
       ["SSL Stripping", "CSRF", "XXE", "Path traversal"], 0),
    QA("Cybersecurity", "Which is asymmetric crypto?",
       ["AES", "ChaCha20", "RSA", "Blowfish"], 2),

    # ---------------- DevOps (8) ----------------
    QA("DevOps", "CI/CD mainly aims to:",
       ["Reduce server cost", "Automate build/test/deploy", "Replace devs", "Encrypt DB"], 1),
    QA("DevOps", "Container orchestration platform:",
       ["Ansible", "Kubernetes", "Terraform", "Packer"], 1),
    QA("DevOps", "Blue/Green deployment reduces:",
       ["Logging", "Downtime & risk", "Traffic", "CPU"], 1),
    QA("DevOps", "Which tool is primarily for config management?",
       ["Terraform", "Ansible", "Vault", "Grafana"], 1),
    QA("DevOps", "Prometheus is used for:",
       ["Tracing", "Metrics scraping", "Log shipping", "Builds"], 1),
    QA("DevOps", "Git strategy allowing short-lived branches merged often:",
       ["Trunk-based", "Gitflow", "Fork-based", "Mono-repo"], 0),
    QA("DevOps", "Canary release sends traffic to:",
       ["All new version", "Subset of users", "Blue env only", "Staging"], 1),
    QA("DevOps", "IaC state management commonly handled by:",
       ["Jenkins", "Terraform state", "Helm", "Kustomize"], 1),

    # ---------------- AI/ML (8) ----------------
    QA("AI/ML", "Best metric for imbalanced binary classes:",
       ["Accuracy", "Precision/Recall or F1", "MSE", "R²"], 1),
    QA("AI/ML", "Regularization mainly helps by:",
       ["Fitting noise", "Preventing overfitting", "I/O speed", "GPU usage"], 1),
    QA("AI/ML", "ReLU activation is:",
       ["Linear", "max(0, x)", "Sigmoid", "Tanh"], 1),
    QA("AI/ML", "Which reduces variance by averaging models?",
       ["Bagging", "Boosting", "Dropout", "BatchNorm"], 0),
    QA("AI/ML", "k in k-NN controls:",
       ["Learning rate", "Neighbors considered", "Depth", "Epochs"], 1),
    QA("AI/ML", "Which is an optimization algorithm?",
       ["Adam", "Softmax", "Dropout", "BatchNorm"], 0),
    QA("AI/ML", "ROC curve plots:",
       ["Precision vs Recall", "TPR vs FPR", "Loss vs Epoch", "MAE vs RMSE"], 1),
    QA("AI/ML", "L1 regularization tends to produce:",
       ["Denser weights", "Sparser weights", "Bigger nets", "Overfit"], 1),

    # ------------- Data Science (8) -------------
    QA("Data Science", "Which plot best shows distribution & outliers?",
       ["Line chart", "Box plot", "Bar chart", "Pie chart"], 1),
    QA("Data Science", "p-value is:",
       ["Prob(null is true)", "Prob(data under null)", "Effect size", "Accuracy"], 1),
    QA("Data Science", "Cross-validation primarily estimates:",
       ["Conf interval", "Generalization performance", "Bias", "Causal effect"], 1),
    QA("Data Science", "Standardization typically transforms features to:",
       ["[0,1]", "Mean 0, var 1", "Binary", "Ranks"], 1),
    QA("Data Science", "Which reduces dimensionality linearly?",
       ["PCA", "t-SNE", "UMAP", "k-means"], 0),
    QA("Data Science", "A/B test with small samples should favor:",
       ["Parametric t-test always", "Power analysis & proper design", "p-hack", "Peeking often"], 1),
    QA("Data Science", "Heteroscedasticity violates which regression assumption?",
       ["Linearity", "Constant variance", "Independence", "Normality"], 1),
    QA("Data Science", "Which metric penalizes over-prediction more if squared?",
       ["MAE", "MSE", "MAPE", "R²"], 1),

    # ------------- General CS (8) -------------
    QA("General CS", "Which OSI layer does TCP operate at?",
       ["Application", "Transport", "Network", "Data Link"], 1),
    QA("General CS", "Big-O of traversing a singly linked list of n?",
       ["O(1)", "O(log n)", "O(n)", "O(n log n)"], 2),
    QA("General CS", "Which protocol resolves domain names to IP?",
       ["HTTP", "DNS", "ARP", "ICMP"], 1),
    QA("General CS", "ACID: the 'I' stands for:",
       ["Integrity", "Isolation", "Idempotency", "Indexing"], 1),
    QA("General CS", "CPU cache levels L1/L2/L3 mainly differ by:",
       ["Voltage", "Size/latency tradeoff", "ISA", "Cores"], 1),
    QA("General CS", "Which file system is journaled by default on many Linux distros?",
       ["ext4", "FAT32", "exFAT", "NTFS"], 0),
    QA("General CS", "UTF-8 is a:",
       ["Hash", "Compression", "Character encoding", "Cipher"], 2),
    QA("General CS", "Docker image layers are:",
       ["Mutable", "Immutable", "Encrypted", "Kernel-level"], 1),
]

def get_random_qa() -> QA:
    """Pick a random category, then a random question from that category."""
    cat = random.choice(CATEGORIES)
    pool = [q for q in BANK if q.category == cat]
    return random.choice(pool)
