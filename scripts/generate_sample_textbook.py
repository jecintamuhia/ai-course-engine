"""Generate a sample machine-learning textbook PDF for pipeline demos.

Writes ``sample_ml_textbook.pdf`` (deterministic content) that exercises
the whole ingestion pipeline: clearly numbered chapter and section
headings (recognised by the structure detector), paragraph-based body
text sized for the chunker, and enough distinct concepts for the AI
topic analysis and curriculum planner.

Usage (from the repo root):

    python scripts/generate_sample_textbook.py [output.pdf]
"""

from __future__ import annotations

import sys
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

OUTPUT_DEFAULT = Path("storage/sample_ml_textbook.pdf")


# ---------------------------------------------------------------------------
# Textbook content (deterministic)
# ---------------------------------------------------------------------------

BOOK_TITLE = "Introduction to Machine Learning"
BOOK_SUBTITLE = (
    "A Practical Foundation in Concepts, Algorithms, and Applications"
)

# Each section: (title, [paragraph, ...])
CHAPTERS: list[tuple[str, list[tuple[str, list[str]]]]] = [
    (
        "Introduction to Machine Learning",
        [
            (
                "What is Machine Learning",
                [
                    "Machine learning is a branch of artificial intelligence that "
                    "gives computers the ability to learn from data without being "
                    "explicitly programmed for every task. A learning algorithm "
                    "examines examples, detects patterns in them, and builds a model "
                    "that can make predictions or decisions about new data.",
                    "The discipline sits at the intersection of statistics, "
                    "computer science, and domain expertise. In contrast to "
                    "traditional rule-based systems, a machine learning system "
                    "improves its performance on a task as it is exposed to more "
                    "relevant data over time.",
                ],
            ),
            (
                "Supervised and Unsupervised Learning",
                [
                    "In supervised learning, the training data includes both inputs "
                    "and their correct outputs, which are called labels. The "
                    "algorithm learns a mapping from inputs to outputs and then "
                    "applies that mapping to new, unseen examples.",
                    "Unsupervised learning works with data that has no labels. The "
                    "goal is to discover hidden structure, such as groups of similar "
                    "items or unusual observations, rather than to predict a known "
                    "target value.",
                    "A third category, reinforcement learning, learns by interacting "
                    "with an environment and receiving rewards or penalties, which "
                    "guides the system toward a long-term strategy.",
                ],
            ),
            (
                "The Machine Learning Workflow",
                [
                    "A typical machine learning project moves through several "
                    "stages: defining the problem, collecting and cleaning data, "
                    "exploring the data, choosing a model, training the model, "
                    "evaluating its performance, and deploying it into a real "
                    "application.",
                    "Each stage can fail in different ways, so practitioners keep "
                    "careful records of their experiments. Reproducibility matters "
                    "as much as accuracy, especially when models will be retrained "
                    "as new data arrives.",
                ],
            ),
        ],
    ),
    (
        "Machine Learning Foundations",
        [
            (
                "Data, Features, and Labels",
                [
                    "Data is the raw material of any machine learning system. A "
                    "dataset is a collection of examples, and each example is "
                    "described by a set of features that capture its relevant "
                    "properties.",
                    "Features must be chosen carefully because the model can only "
                    "learn from the information it is given. Redundant or noisy "
                    "features can slow training and harm generalization, while a "
                    "good feature set encodes the structure the model needs to "
                    "discriminate between classes or estimate quantities.",
                ],
            ),
            (
                "The Bias-Variance Trade-Off",
                [
                    "Bias measures how far a model's predictions are, on average, "
                    "from the true values. A high-bias model is too simple and "
                    "underfits the data, missing important relationships.",
                    "Variance measures how much the model's predictions change when "
                    "it is trained on different samples of the same data. A "
                    "high-variance model is too flexible and overfits, memorizing "
                    "noise instead of the underlying pattern.",
                    "The bias-variance trade-off guides model selection: a good "
                    "model balances both sources of error so that it generalizes "
                    "well to unseen data.",
                ],
            ),
            (
                "Training, Validation, and Test Sets",
                [
                    "To estimate how well a model will perform on new data, "
                    "practitioners split their data into separate sets. The training "
                    "set fits the model parameters, the validation set tunes "
                    "hyperparameters and detects overfitting, and the test set gives "
                    "the final unbiased performance estimate.",
                    "Standard practice is to withhold the test set until the very "
                    "end, so that decisions made during development cannot leak into "
                    "the final evaluation.",
                ],
            ),
        ],
    ),
    (
        "Regression",
        [
            (
                "Linear Regression",
                [
                    "Linear regression models the relationship between input "
                    "features and a continuous target as a straight line or "
                    "hyperplane. The model learns a set of weights such that the "
                    "predicted values minimize the sum of squared errors.",
                    "The method of least squares provides a closed-form solution for "
                    "these weights, making linear regression fast to fit and easy to "
                    "interpret.",
                ],
            ),
            (
                "Gradient Descent",
                [
                    "For larger problems, a closed-form solution becomes too "
                    "expensive. Gradient descent instead adjusts the weights "
                    "iteratively, moving each step in the direction that reduces the "
                    "cost the most.",
                    "The learning rate controls the size of each step. Too large a "
                    "rate causes the optimization to overshoot, while too small a "
                    "rate makes training slow to converge.",
                ],
            ),
            (
                "Evaluating Regression Models",
                [
                    "Common metrics for regression include mean squared error, root "
                    "mean squared error, and the coefficient of determination R "
                    "squared.",
                    "No single metric is perfect; robust evaluation also considers "
                    "residual plots and how errors behave across different regions "
                    "of the data.",
                ],
            ),
        ],
    ),
    (
        "Classification",
        [
            (
                "Logistic Regression",
                [
                    "Logistic regression predicts the probability that an example "
                    "belongs to a particular class. It applies a sigmoid function to "
                    "a linear combination of the features to keep the output between "
                    "zero and one.",
                    "Although its name contains the word regression, it is a "
                    "classification algorithm used heavily in medicine, finance, and "
                    "marketing because its outputs are easily interpreted as "
                    "probabilities.",
                ],
            ),
            (
                "Support Vector Machines",
                [
                    "A support vector machine finds the hyperplane that separates "
                    "classes with the widest possible margin. The examples closest "
                    "to the boundary, called support vectors, define the decision "
                    "surface.",
                    "Kernels allow the model to operate in a higher-dimensional "
                    "space, enabling it to separate data that is not linearly "
                    "separable in its original representation.",
                ],
            ),
            (
                "Decision Trees and Ensembles",
                [
                    "Decision trees split the feature space into regions by asking "
                    "a series of if-then questions. They are easy to interpret but "
                    "prone to overfitting when grown too deep.",
                    "Ensemble methods, such as random forests and gradient "
                    "boosting, combine many weak learners into one strong model, "
                    "reducing variance and improving accuracy at the cost of some "
                    "interpretability.",
                ],
            ),
        ],
    ),
    (
        "Unsupervised Learning",
        [
            (
                "Clustering",
                [
                    "Clustering groups similar examples together so that items in "
                    "the same group are more alike than items in different groups. "
                    "It is widely used for customer segmentation, image compression, "
                    "and exploratory data analysis.",
                    "The k-means algorithm alternates between assigning each point "
                    "to its nearest cluster center and recomputing the centers until "
                    "the assignment stabilizes.",
                ],
            ),
            (
                "Dimensionality Reduction",
                [
                    "High-dimensional data is hard to visualize and often contains "
                    "redundant features. Dimensionality reduction methods project "
                    "the data into a lower-dimensional space while preserving as "
                    "much structure as possible.",
                    "Principal component analysis finds the directions of greatest "
                    "variance and uses them as a new coordinate system, which "
                    "removes correlation and can denoise the data.",
                ],
            ),
            (
                "Anomaly Detection",
                [
                    "Anomaly detection seeks examples that deviate strongly from "
                    "expected behavior. It is applied to fraud detection, network "
                    "intrusion detection, and industrial quality control.",
                    "Unsupervised anomaly detection builds a model of normal data "
                    "and then flags points that the model assigns low probability.",
                ],
            ),
        ],
    ),
    (
        "Model Evaluation and Selection",
        [
            (
                "Cross-Validation",
                [
                    "Cross-validation repeatedly splits the data into training and "
                    "validation folds, fitting the model on each training fold and "
                    "measuring performance on the validation fold.",
                    "The average performance across folds is a more reliable "
                    "estimate of generalization than a single split, especially "
                    "when the data is small or noisy.",
                ],
            ),
            (
                "Metrics for Imbalanced Data",
                [
                    "When classes are heavily imbalanced, accuracy can be "
                    "misleading. Precision, recall, and the F1 score describe how "
                    "well a model finds the minority class without drowning in false "
                    "positives.",
                    "The precision-recall curve and the area under it summarize "
                    "this behavior across all classification thresholds.",
                ],
            ),
            (
                "Regularization",
                [
                    "Regularization adds a penalty to the cost function that "
                    "discourages large weights. L1 regularization encourages sparse "
                    "models, while L2 regularization shrinks weights smoothly.",
                    "Choosing the right strength of regularization balances "
                    "underfitting and overfitting and is usually done with "
                    "cross-validation.",
                ],
            ),
        ],
    ),
    (
        "Neural Networks and Deep Learning",
        [
            (
                "Neurons and Activation Functions",
                [
                    "An artificial neuron computes a weighted sum of its inputs and "
                    "passes the result through an activation function. Activation "
                    "functions introduce the nonlinearity that lets networks "
                    "represent complex functions.",
                    "Common choices include the sigmoid, the hyperbolic tangent, "
                    "and the rectified linear unit, each with different "
                    "characteristics for training stability and expressiveness.",
                ],
            ),
            (
                "Training Neural Networks",
                [
                    "Neural networks are trained with the backpropagation "
                    "algorithm, which computes the gradient of the loss with respect "
                    "to every weight and updates the weights in the direction that "
                    "reduces the loss.",
                    "Minibatches speed up training by updating the weights after "
                    "averaging gradients over small random subsets of the data, and "
                    "this stochasticity often helps the optimizer find better "
                    "solutions.",
                ],
            ),
            (
                "Convolutional Networks",
                [
                    "Convolutional neural networks use learned filters that slide "
                    "across the input, detecting local patterns such as edges and "
                    "textures. They are the dominant architecture for image "
                    "recognition tasks.",
                    "Pooling layers downsample the feature maps, giving the network "
                    "a degree of translation invariance and reducing the number of "
                    "parameters that must be learned.",
                ],
            ),
        ],
    ),
    (
        "Practical Applications and Ethics",
        [
            (
                "Deploying Machine Learning Models",
                [
                    "Deploying a model requires monitoring its inputs and outputs "
                    "over time, because real-world data drifts and model performance "
                    "degrades as distributions change.",
                    "Modern teams package models as services, log predictions and "
                    "features, and put retraining pipelines in place so the model "
                    "can be refreshed automatically.",
                ],
            ),
            (
                "Fairness and Bias",
                [
                    "Models trained on historical data can inherit and amplify "
                    "societal biases. Practitioners must audit training data and "
                    "model outputs for disparate impact across protected groups.",
                    "Fairness considerations begin at problem framing and continue "
                    "through data collection, feature engineering, evaluation, and "
                    "deployment.",
                ],
            ),
            (
                "Privacy and Security",
                [
                    "Machine learning raises privacy concerns because models can "
                    "memorize information from their training data. Techniques such "
                    "as differential privacy and federated learning reduce these "
                    "risks.",
                    "Adversarial examples exploit model blind spots: small, "
                    "carefully chosen perturbations to an input can flip a model's "
                    "prediction while remaining imperceptible to humans.",
                ],
            ),
        ],
    ),
]


def _build_story() -> list:
    """Return the reportlab flowables for the textbook pages."""
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "TitleCustom",
        parent=styles["Title"],
        spaceAfter=18,
    )
    subtitle_style = ParagraphStyle(
        "SubtitleCustom",
        parent=styles["Normal"],
        fontSize=13,
        leading=18,
        textColor="#555555",
        spaceAfter=24,
    )
    chapter_style = ParagraphStyle(
        "ChapterHeading",
        parent=styles["Heading1"],
        fontSize=22,
        spaceBefore=0,
        spaceAfter=16,
    )
    section_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=14,
        spaceBefore=12,
        spaceAfter=6,
    )
    body_style = styles["BodyText"]

    story: list = []

    # Title page only - no table of contents, because "Chapter N:"
    # lines on a contents page would be misdetected as chapter boundaries
    # by the deterministic structure detector.
    story.append(Spacer(1, 2 * inch))
    story.append(Paragraph(BOOK_TITLE, title_style))
    story.append(Paragraph(BOOK_SUBTITLE, subtitle_style))
    story.append(PageBreak())

    # Body.
    for chapter_index, (chapter_title, sections) in enumerate(
        CHAPTERS, start=1
    ):
        story.append(
            Paragraph(
                f"Chapter {chapter_index}: {chapter_title}",
                chapter_style,
            )
        )
        for section_index, (section_title, paragraphs) in enumerate(
            sections, start=1
        ):
            story.append(
                Paragraph(
                    f"{chapter_index}.{section_index} {section_title}",
                    section_style,
                )
            )
            for text in paragraphs:
                story.append(Paragraph(text, body_style))
                story.append(Spacer(1, 6))
        story.append(PageBreak())

    return story


def generate(output_path: Path) -> Path:
    """Render the sample textbook PDF to ``output_path``."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=inch,
        rightMargin=inch,
        topMargin=inch,
        bottomMargin=inch,
        title=BOOK_TITLE,
        author="AI Course Engine Demo",
    )
    doc.build(_build_story())
    return output_path


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else OUTPUT_DEFAULT
    path = generate(target)
    print(f"Wrote sample textbook to {path}")